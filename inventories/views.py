import hashlib
import io
import json
import re

from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import connection
from django.db.models import Prefetch, Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import (
    DetailView,
    RedirectView,
    TemplateView,
    View,
)
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import ModelFormMixin
from django_tomselect.autocompletes import AutocompleteModelView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from layer_manager.models import Layer, LayerAggregatedValue
from maps.models import Catchment, GeoDataset, Region
from maps.serializers import BaseResultMapSerializer
from maps.views import GeoDataSetAutocompleteView, MapMixin
from materials.models import Material, SampleSeries
from utils.object_management.permissions import filter_queryset_for_user
from utils.object_management.policy import decide
from utils.object_management.services import content_mutation
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectUpdateView,
    get_tomselect_filter_value,
)
from utils.views import BreadcrumbContextMixin, build_breadcrumb_context

from .algorithms import GENERIC_MODULE_PATH
from .evaluations import ScenarioResult
from .evaluator import (
    DATASET_BASE_KINDS,
    FILTER_OPERATORS,
    LEGACY_FUNCTION_BASE_KINDS,
    BaseKind,
    available_base_kinds,
)
from .exceptions import BlockedRunningScenario, InvalidParameterValue
from .filters import ScenarioFilterSet
from .forms import (
    ScenarioInventoryConfigurationAddForm,
    ScenarioInventoryConfigurationUpdateForm,
    ScenarioModelForm,
    SeasonalDistributionModelForm,
)
from .models import (
    FeedstockNotImplemented,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    InventoryStream,
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
    StreamFactor,
    StreamFilter,
)
from .tasks import start_inventory_run


def _get_posted_object_or_404(model, pk, queryset=None):
    """Fetch an object by an id taken from request data.

    ``get_object_or_404`` only translates ``DoesNotExist``; ids arriving as
    POST strings can also fail with ``ValueError``/``TypeError`` before the
    query reaches the database, so catch those too. ``queryset`` optionally
    restricts the lookup — e.g. to objects visible to the requesting user.
    """
    manager = model.objects if queryset is None else queryset
    try:
        return manager.get(pk=pk)
    except (model.DoesNotExist, ValueError, TypeError):
        raise Http404 from None


def _posted_sample_series(request, feedstock):
    """Resolve the optional ``sample_series`` POST field.

    The series is the temporal profile of the configured feedstock material,
    so it must belong to it. Returns ``None`` when no series was posted.
    """
    raw = request.POST.get("sample_series")
    if not raw:
        return None
    series = _get_posted_object_or_404(SampleSeries, raw)
    if series.material_id != feedstock.pk:
        raise InvalidParameterValue(
            "The sample series does not belong to the selected feedstock."
        )
    return series


class InventoriesExplorerView(BreadcrumbContextMixin, TemplateView):
    template_name = "inventories_explorer.html"
    breadcrumb_module_label = "Inventories"
    breadcrumb_page_title = "Inventories"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["scenario_count"] = Scenario.objects.filter(
            publication_status="published"
        ).count()
        context["algorithm_count"] = InventoryAlgorithm.objects.count()
        return context


class SeasonalDistributionCreateView(UserCreatedObjectCreateView):
    form_class = SeasonalDistributionModelForm
    template_name = "seasonal_distribution_create.html"
    permission_required = "distributions.add_temporaldistribution"

    def get_success_url(self):
        return f"/inventories/materials/{self.kwargs['material_pk']}"


# ----------- Inventory Algorithm Utils --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class InventoryAlgorithmAutocompleteView(AutocompleteModelView):
    model = InventoryAlgorithm
    search_lookups = ["name__icontains"]
    value_fields = [
        "name",
    ]
    ordering = ["name"]
    allow_anonymous = True
    page_size = 15

    def __init_subclass__(cls, **kwargs):
        """Preserve inherited search/value fields across subclasses.

        django-tomselect 2026.1.3 resets list attributes in
        ``AutocompleteModelView.__init_subclass__`` for subclasses that do not
        define them directly. Save inherited values before calling super and
        restore them afterwards.
        """
        saved = {}
        for attr in ("search_lookups", "value_fields"):
            if attr not in cls.__dict__:
                for base in cls.__mro__[1:]:
                    if attr in base.__dict__:
                        saved[attr] = list(base.__dict__[attr])
                        break

        super().__init_subclass__(**kwargs)

        for attr, value in saved.items():
            setattr(cls, attr, value)


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedScenarioFilterView(PublishedObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet
    explorer_url = reverse_lazy("inventories-explorer")


class PrivateScenarioFilterView(PrivateObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet
    explorer_url = reverse_lazy("inventories-explorer")


class ScenarioCreateView(UserCreatedObjectCreateView):
    form_class = ScenarioModelForm
    permission_required = "inventories.add_scenario"


def scenario_presentation_context(scenario, user):
    """Region, catchment and showcase of ``scenario`` that ``user`` may read."""

    def visible(model, pk):
        if pk is None:
            return None
        return filter_queryset_for_user(model.objects.filter(pk=pk), user).first()

    showcase_model = Scenario._meta.get_field("showcase").related_model
    return {
        "visible_region": visible(Region, scenario.region_id),
        "visible_catchment": visible(Catchment, scenario.catchment_id),
        "visible_showcase": visible(showcase_model, scenario.showcase_id),
    }


def inventories_for_template(config):
    """Flatten ``Scenario.configuration_for_template()`` into one entry per inventory."""
    return [
        {
            "feedstock": feedstock,
            "algorithm": algorithm,
            "parameters": [
                (parameter, value)
                for parameter, value in parameters.items()
                if parameter is not None
            ],
        }
        for feedstock, algorithms in config.items()
        for algorithm, parameters in algorithms.items()
    ]


class ScenarioMapMixin(MapMixin):
    """Draws only the scenario's region and catchment that the user may read."""

    def _visible_feature_id(self, model, pk):
        if pk is None:
            return None
        return (
            filter_queryset_for_user(model.objects.filter(pk=pk), self.request.user)
            .values_list("pk", flat=True)
            .first()
        )

    def get_region_feature_id(self):
        return self._visible_feature_id(Region, self.object.region_id)

    def get_catchment_feature_id(self):
        return self._visible_feature_id(Catchment, self.object.catchment_id)


class ScenarioDetailView(ScenarioMapMixin, UserCreatedObjectDetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    object = None
    config = None
    allow_edit = False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context["config"] = self.config
        context["inventories"] = inventories_for_template(self.config)
        context["streams"] = self.object.streams.select_related(
            "material", "geodataset"
        ).prefetch_related("factors", "filters")
        context["allow_edit"] = self.allow_edit
        context.update(scenario_presentation_context(self.object, request.user))
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        if not decide(request.user, "edit", scenario).allowed:
            return HttpResponseForbidden()
        start_inventory_run(scenario.id)
        return redirect("scenario-result", scenario.id)


class ScenarioEvaluationConflictMixin:
    """Active-evaluation guards map to 409 instead of propagating 500s."""

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except BlockedRunningScenario:
            return HttpResponse("Evaluation is still in progress.", status=409)


class ScenarioUpdateView(ScenarioEvaluationConflictMixin, UserCreatedObjectUpdateView):
    model = Scenario
    form_class = ScenarioModelForm


class ScenarioModalDeleteView(
    ScenarioEvaluationConflictMixin, UserCreatedObjectModalDeleteView
):
    model = Scenario


# ----------- Scenario Utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Scenario


CUSTOM_PARAMETER_VALUE = "custom"

KWARG_NAME_PATTERN = re.compile(r"^[A-Za-z_]\w{0,27}$")


def _parse_kwarg_rows(request):
    """Parse the free-form factor rows of the generic add-inventory form.

    Expects aligned ``kwarg_name``/``kwarg_value`` lists; optional
    ``kwarg_unit``/``kwarg_standard_deviation`` lists are padded. Returns
    ``[{"name", "value", "unit", "standard_deviation"}]`` dicts. A row filled
    from a preset posts the preset's numbers like any other row.
    """
    names = request.POST.getlist("kwarg_name")
    raw_values = request.POST.getlist("kwarg_value")
    if len(names) != len(raw_values):
        raise InvalidParameterValue("Incomplete factor row.")
    # Optional lists may be shorter — pad them.
    units = request.POST.getlist("kwarg_unit")
    raw_stds = request.POST.getlist("kwarg_standard_deviation")
    units += [""] * (len(names) - len(units))
    raw_stds += [""] * (len(names) - len(raw_stds))
    specs = []
    for name, raw_value, unit, raw_std in zip(
        names, raw_values, units, raw_stds, strict=False
    ):
        name = name.strip()
        if not KWARG_NAME_PATTERN.match(name):
            raise InvalidParameterValue(
                f"Invalid parameter name '{name}'. Use letters, digits and "
                "underscores only, starting with a letter (max 28 characters)."
            )
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise InvalidParameterValue(
                f"A numeric value is required for parameter '{name}'."
            ) from None
        try:
            std = float(raw_std) if raw_std not in (None, "") else None
        except ValueError:
            raise InvalidParameterValue(
                f"The standard deviation for parameter '{name}' must be numeric."
            ) from None
        if len(unit) > 40:
            raise InvalidParameterValue(
                f"The unit for parameter '{name}' is too long (max 40 characters)."
            )
        specs.append(
            {
                "name": name,
                "value": value,
                "unit": unit.strip(),
                "standard_deviation": std,
            }
        )
    return specs


def _parse_stream_base(request, base_kind, geodataset):
    """Fields of the stream that describe a base quantity read from a column."""
    from .algorithms import InventoryAlgorithms

    if base_kind != BaseKind.COLUMN_SUM:
        return {}
    column = request.POST.get("base_column", "").strip()
    if column not in InventoryAlgorithms.numeric_columns(geodataset):
        raise InvalidParameterValue(
            "Choose a numeric column of this dataset as base quantity."
        )
    unit = request.POST.get("base_unit", "").strip()
    if len(unit) > 40:
        raise InvalidParameterValue("The unit of the base quantity is too long.")
    return {"base_column": column, "base_unit": unit}


def _parse_stream_filter(request, geodataset):
    """The optional feature filter of the add-inventory form, or None.

    Restricts the stream to a subset of features — e.g. one crop out of many
    in a parcels dataset.
    """
    from .algorithms import InventoryAlgorithms

    column = request.POST.get("filter_column", "").strip()
    value = request.POST.get("filter_value", "").strip()
    operator = request.POST.get("filter_operator", "").strip() or "eq"
    if not (column or value):
        return None
    if not (column and value):
        raise InvalidParameterValue(
            "Both a filter column and a filter value are required."
        )
    if operator not in FILTER_OPERATORS:
        raise InvalidParameterValue(f"Unknown filter operator '{operator}'.")
    valid_columns = {c["name"] for c in InventoryAlgorithms.feature_columns(geodataset)}
    if column not in valid_columns:
        raise InvalidParameterValue(
            f"'{column}' is not a filterable column of this dataset."
        )
    if len(value) > 255:
        raise InvalidParameterValue("The feature filter is too long.")
    return {"column": column, "operator": operator, "value": value}


def create_custom_parameter_value(request, parameter):
    """Creates a user-provided value for a parameter from POSTed custom inputs."""
    if parameter.inventoryalgorithmparametervalue_set.exclude(
        type=InventoryAlgorithmParameterValue.ValueType.NUMERIC
    ).exists():
        raise InvalidParameterValue(
            f"Parameter '{parameter}' uses categorical presets and does not "
            "accept custom values."
        )
    prefix = f"parameter_{parameter.pk}_custom"
    try:
        value = float(request.POST.get(f"{prefix}_value"))
    except (TypeError, ValueError):
        raise InvalidParameterValue(
            f"A numeric value is required for parameter '{parameter}'."
        ) from None
    raw_std = request.POST.get(f"{prefix}_standard_deviation")
    try:
        standard_deviation = float(raw_std) if raw_std not in (None, "") else None
    except ValueError:
        raise InvalidParameterValue(
            f"The standard deviation for parameter '{parameter}' must be numeric."
        ) from None
    source = request.POST.get(f"{prefix}_source", "").strip() or "User assumption"
    return InventoryAlgorithmParameterValue.objects.create(
        name="",
        parameter=parameter,
        value=value,
        standard_deviation=standard_deviation,
        source=source,
        default=False,
        is_custom=True,
    )


def resolve_parameter_values(request, algorithm, scenario):
    """
    Maps the algorithm's parameters to the values posted in the configuration form.
    Each parameter may either reference a curated preset, a custom value already
    configured in the given scenario, or the sentinel 'custom', in which case a
    user-provided InventoryAlgorithmParameterValue is created.
    """
    values = {}
    for parameter in algorithm.inventoryalgorithmparameter_set.all():
        posted = request.POST.get(f"parameter_{parameter.pk}")
        if not posted:
            continue
        if posted == CUSTOM_PARAMETER_VALUE:
            value = create_custom_parameter_value(request, parameter)
        else:
            value = _get_posted_object_or_404(InventoryAlgorithmParameterValue, posted)
            scenario_customs = ScenarioInventoryConfiguration.objects.filter(
                scenario=scenario, inventory_parameter=parameter
            ).values("inventory_value_id")
            if not InventoryAlgorithmParameterValue.objects.filter(
                Q(is_custom=False) | Q(id__in=scenario_customs),
                id=value.pk,
                parameter=parameter,
            ).exists():
                raise InvalidParameterValue(
                    f"Invalid value for parameter '{parameter}'."
                )
        values[parameter] = [value]
    return values


@login_required
def get_evaluation_status(request, task_id=None):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result,
        "task_info": task_result.info,
    }
    return JsonResponse(result, status=200)


class ScenarioEditPermissionMixin(ScenarioEvaluationConflictMixin):
    """test_func delegating to the central ``edit`` decision on the scenario
    named by ``scenario_kwarg``."""

    scenario_kwarg = "scenario_pk"
    scenario = None

    def test_func(self):
        self.scenario = get_object_or_404(
            Scenario, id=self.kwargs.get(self.scenario_kwarg)
        )
        return decide(self.request.user, "edit", self.scenario).allowed


class ScenarioAddInventoryAlgorithmView(
    LoginRequiredMixin,
    ScenarioEditPermissionMixin,
    UserPassesTestMixin,
    TemplateResponseMixin,
    ModelFormMixin,
    View,
):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationAddForm
    template_name = "scenario_configuration_add.html"
    object = None
    scenario_kwarg = "pk"

    def post(self, request, *args, **kwargs):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("pk"))
        choice = request.POST.get("algorithm_choice", "")
        if not choice:
            if request.POST.get("generic_function"):
                choice = f"generic:{request.POST.get('generic_function')}"
            elif request.POST.get("inventory_algorithm"):
                choice = f"algo:{request.POST.get('inventory_algorithm')}"
        kind, _, ref = choice.partition(":")
        if kind == "generic":
            # The former generic functions are base quantities of a stream.
            base_kind = LEGACY_FUNCTION_BASE_KINDS.get(ref)
            if base_kind is None:
                return HttpResponseBadRequest("Unknown generic function.")
            return self._post_stream(request, scenario, base_kind)
        if kind == "stream":
            return self._post_stream(request, scenario, ref)
        feedstock = _get_posted_object_or_404(Material, request.POST.get("feedstock"))
        algorithm = _get_posted_object_or_404(
            InventoryAlgorithm,
            ref or None,
            queryset=InventoryAlgorithm.objects.exclude(
                source_module=GENERIC_MODULE_PATH
            ),
        )
        if (
            not filter_queryset_for_user(GeoDataset.objects.all(), request.user)
            .filter(pk=algorithm.geodataset_id)
            .exists()
        ):
            raise Http404
        try:
            sample_series = _posted_sample_series(request, feedstock)
            # The configuration rows are owned children of the scenario:
            # their create writes inside the scenario's content_mutation
            # boundary — the shared InventoryAlgorithmParameter(Value) rows
            # stay unregistered config entities inside the same atomic.
            with content_mutation(
                request.user, scenario, action="edit"
            ) as locked_scenario:
                values = resolve_parameter_values(request, algorithm, locked_scenario)
                locked_scenario.add_inventory_algorithm(
                    feedstock, algorithm, values, sample_series=sample_series
                )
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        except FeedstockNotImplemented:
            raise Http404 from None
        return redirect("scenario-detail", pk=scenario.pk)

    def _post_stream(self, request, scenario, base_kind):
        """Store the posted dataset, filter and factor rows as a stream."""
        if base_kind not in DATASET_BASE_KINDS:
            return HttpResponseBadRequest("Unknown base quantity.")
        geodataset = _get_posted_object_or_404(
            GeoDataset,
            request.POST.get("geodataset"),
            queryset=filter_queryset_for_user(GeoDataset.objects.all(), request.user),
        )
        if not scenario.compatible_geodatasets().filter(pk=geodataset.pk).exists():
            return HttpResponseBadRequest(
                "The geodataset does not cover the scenario region."
            )
        if base_kind not in available_base_kinds(geodataset):
            return HttpResponseBadRequest(
                f"'{BaseKind(base_kind).label}' does not apply to this dataset."
            )
        feedstock = _get_posted_object_or_404(Material, request.POST.get("feedstock"))
        try:
            sample_series = _posted_sample_series(request, feedstock)
            factor_specs = _parse_kwarg_rows(request)
            stream_fields = _parse_stream_base(request, base_kind, geodataset)
            filter_spec = _parse_stream_filter(request, geodataset)
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        symbols = [spec["name"] for spec in factor_specs]
        if len(set(symbols)) != len(symbols):
            return HttpResponseBadRequest("Each factor name may be used only once.")

        with content_mutation(request.user, scenario, action="edit") as locked_scenario:
            stream = InventoryStream.objects.create(
                scenario=locked_scenario,
                material=feedstock,
                sample_series=sample_series,
                base_kind=base_kind,
                geodataset=geodataset,
                **stream_fields,
            )
            for order, spec in enumerate(factor_specs):
                StreamFactor.objects.create(
                    stream=stream,
                    symbol=spec["name"],
                    value=spec["value"],
                    standard_deviation=spec["standard_deviation"],
                    unit=spec["unit"],
                    source="User assumption",
                    order=order,
                )
            if filter_spec:
                StreamFilter.objects.create(stream=stream, **filter_spec)
        return redirect("scenario-detail", pk=scenario.pk)

    def get_object(self, **kwargs):
        return get_object_or_404(Scenario, pk=self.kwargs.get("pk"))

    def get_initial(self):
        return {
            # Generic functions materialize their algorithm on submit, so any
            # material may be picked — the dropdown itself is served by the
            # visibility-filtered material autocomplete.
            "feedstocks": Material.objects.all(),
            "scenario": self.object,
        }

    def get_context_data(self, **kwargs):
        context = {
            "scenario": self.object,
            "form": self.get_form(),
            "form_title": f'Add an algorithm to the scenario "{self.object.name}"',
        }
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioAlgorithmConfigurationUpdateView(
    LoginRequiredMixin,
    ScenarioEditPermissionMixin,
    UserPassesTestMixin,
    TemplateResponseMixin,
    ModelFormMixin,
    View,
):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationUpdateForm
    template_name = "scenario_configuration_update.html"
    object = None

    def post(self, request, *args, **kwargs):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        current_algorithm = get_object_or_404(
            InventoryAlgorithm, id=self.kwargs.get("algorithm_pk")
        )
        current_feedstock = get_object_or_404(
            Material, id=self.kwargs.get("feedstock_pk")
        )
        feedstock = _get_posted_object_or_404(Material, request.POST.get("feedstock"))
        new_algorithm = _get_posted_object_or_404(
            InventoryAlgorithm, request.POST.get("inventory_algorithm")
        )
        try:
            sample_series = _posted_sample_series(request, feedstock)
            # The remove+add pair replaces one configuration atomically
            # inside the scenario's content_mutation boundary.
            with content_mutation(
                request.user, scenario, action="edit"
            ) as locked_scenario:
                values = resolve_parameter_values(
                    request, new_algorithm, locked_scenario
                )
                locked_scenario.remove_inventory_algorithm(
                    current_algorithm, current_feedstock
                )
                locked_scenario.add_inventory_algorithm(
                    feedstock, new_algorithm, values, sample_series=sample_series
                )
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        except FeedstockNotImplemented:
            raise Http404 from None
        return redirect("scenario-detail", pk=scenario.pk)

    def get_object(self, **kwargs):
        return get_object_or_404(Scenario, pk=self.kwargs.get("scenario_pk"))

    def get_initial(self):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        algorithm = get_object_or_404(
            InventoryAlgorithm, id=self.kwargs.get("algorithm_pk")
        )
        feedstock = get_object_or_404(Material, id=self.kwargs.get("feedstock_pk"))
        config = scenario.inventory_algorithm_config(algorithm, feedstock)
        return config

    def get_context_data(self, **kwargs):
        context = self.get_initial()
        context["form"] = self.get_form()
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioRemoveInventoryAlgorithmView(
    LoginRequiredMixin, ScenarioEditPermissionMixin, UserPassesTestMixin, View
):
    scenario = None
    algorithm = None
    feedstock = None

    def post(self, request, *args, **kwargs):
        self.scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        self.algorithm = get_object_or_404(
            InventoryAlgorithm, id=self.kwargs.get("algorithm_pk")
        )
        self.feedstock = get_object_or_404(Material, id=self.kwargs.get("feedstock_pk"))
        # Removing the configuration rows is a content edit on the scenario
        # root: the central decide inside the boundary re-checks the lock.
        with content_mutation(
            request.user, self.scenario, action="edit"
        ) as locked_scenario:
            locked_scenario.remove_inventory_algorithm(
                algorithm=self.algorithm, feedstock=self.feedstock
            )
        return redirect("scenario-detail", pk=self.scenario.id)


class ScenarioRemoveStreamView(
    LoginRequiredMixin, ScenarioEditPermissionMixin, UserPassesTestMixin, View
):
    def post(self, request, *args, **kwargs):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        stream = get_object_or_404(
            InventoryStream, id=self.kwargs.get("stream_pk"), scenario=scenario
        )
        # Removing a stream is a content edit on the scenario root: the
        # central decide inside the boundary re-checks the lock.
        with content_mutation(request.user, scenario, action="edit"):
            stream.delete()
        return redirect("scenario-detail", pk=scenario.id)


class ScenarioGeoDataSetAutocompleteView(GeoDataSetAutocompleteView):
    """GeoDataset autocomplete scoped to datasets covering a scenario's region.

    The widget passes the scenario id via either ``filter_by`` or
    ``exclude_by`` and an optional feedstock id via ``filter_by``. Every
    dataset of the scenario region or of a region enclosing it is offered;
    several inventories of one material can be built on one dataset.
    """

    def apply_filters(self, queryset):
        scenario_id = get_tomselect_filter_value(
            self, lookup="scenario_id"
        ) or get_tomselect_filter_value(self, use_excludes=True, lookup="scenario_id")
        feedstock_id = get_tomselect_filter_value(self, lookup="feedstock_id")

        if not scenario_id:
            return GeoDataset.objects.none()

        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            return GeoDataset.objects.none()

        if feedstock_id and not Material.objects.filter(pk=feedstock_id).exists():
            return GeoDataset.objects.none()

        return scenario.compatible_geodatasets(queryset)


class ScenarioInventoryAlgorithmAutocompleteView(InventoryAlgorithmAutocompleteView):
    """InventoryAlgorithm autocomplete filtered by geodataset and feedstock.

    The form widget passes:
    - geodataset via ``filter_by``
    - feedstock via ``exclude_by``
    """

    def apply_filters(self, queryset):
        """Return InventoryAlgorithms matching the given geodataset and feedstock.

        Note: This does not check if the algorithm is already configured for a scenario.
        Duplicate prevention is handled by form validation.
        """
        geodataset_id = get_tomselect_filter_value(self, lookup="geodataset_id")
        feedstock_id = get_tomselect_filter_value(
            self, use_excludes=True, lookup="feedstock_id"
        )

        if not (geodataset_id and feedstock_id):
            return InventoryAlgorithm.objects.none()

        try:
            feedstock = Material.objects.get(pk=feedstock_id)
            geodataset = GeoDataset.objects.get(pk=geodataset_id)
        except (Material.DoesNotExist, GeoDataset.DoesNotExist):
            return InventoryAlgorithm.objects.none()

        return InventoryAlgorithm.objects.filter(
            feedstocks=feedstock,
            geodataset=geodataset,
        )


def _factor_presets(scenario_id, geodataset, base_kind):
    """Factors already used in the scenario for this dataset and base
    quantity, in the shape the factor editor reads its presets from.

    Presets never cross scenarios, so the assumptions of other users'
    scenarios stay private.
    """
    if scenario_id is None:
        return []
    presets = {}
    factors = StreamFactor.objects.filter(
        stream__scenario_id=scenario_id,
        stream__geodataset=geodataset,
        stream__base_kind=base_kind,
    ).order_by("pk")
    for factor in factors:
        preset = presets.setdefault(
            (factor.symbol, factor.unit),
            {"short_name": factor.symbol, "unit": factor.unit, "values": []},
        )
        value = {
            "id": factor.pk,
            "name": "",
            "value": factor.value,
            "standard_deviation": factor.standard_deviation,
            "source": factor.source,
        }
        known = {(v["value"], v["standard_deviation"]) for v in preset["values"]}
        if (value["value"], value["standard_deviation"]) not in known:
            preset["values"].append(value)
    return list(presets.values())


class GeoDatasetFunctionsAPIView(LoginRequiredMixin, APIView):
    """JSON endpoint describing how an inventory can be built on a
    GeoDataset: the base quantities it can measure, its filterable and
    numeric columns, and the algorithms registered on the dataset."""

    def get(self, request, geodataset_pk):
        from .algorithms import InventoryAlgorithms

        geodataset = get_object_or_404(
            filter_queryset_for_user(GeoDataset.objects.all(), request.user),
            pk=geodataset_pk,
        )

        scenario_id = request.query_params.get("scenario")
        if not (
            scenario_id
            and scenario_id.isascii()
            and scenario_id.isdigit()
            and filter_queryset_for_user(Scenario.objects.all(), request.user)
            .filter(pk=scenario_id)
            .exists()
        ):
            scenario_id = None

        functions = [
            {
                "base_kind": base_kind,
                "name": BaseKind(base_kind).label,
                "parameters": _factor_presets(scenario_id, geodataset, base_kind),
            }
            for base_kind in available_base_kinds(geodataset)
        ]

        # Generic count and area inventories are streams now; their former
        # algorithm records are no longer offered.
        algorithms = InventoryAlgorithm.objects.filter(geodataset=geodataset).exclude(
            source_module=GENERIC_MODULE_PATH
        )
        feedstock_id = request.query_params.get("feedstock")
        if feedstock_id:
            try:
                feedstock = Material.objects.get(pk=feedstock_id)
                algorithms = algorithms.filter(feedstocks=feedstock)
            except Material.DoesNotExist:
                algorithms = algorithms.none()
            else:
                if scenario_id is not None:
                    # An algorithm is configured once per material.
                    algorithms = algorithms.exclude(
                        pk__in=ScenarioInventoryConfiguration.objects.filter(
                            scenario_id=scenario_id,
                            feedstock=feedstock,
                            geodataset=geodataset,
                        ).values("inventory_algorithm_id")
                    )
        try:
            columns = InventoryAlgorithms.feature_columns(geodataset)
        except Exception:
            columns = []
        try:
            numeric_columns = InventoryAlgorithms.numeric_columns(geodataset)
        except Exception:
            numeric_columns = []
        return Response(
            {
                "geometry_family": InventoryAlgorithms.geometry_family(geodataset),
                "functions": functions,
                "algorithms": [
                    {"id": algorithm.pk, "name": str(algorithm)}
                    for algorithm in algorithms.order_by("name").distinct()
                ],
                "columns": columns,
                "numeric_columns": numeric_columns,
                "filter_operators": [
                    {"value": value, "label": label}
                    for value, label in FILTER_OPERATORS.items()
                ],
            }
        )


class InventoryAlgorithmParametersAPIView(APIView):
    """JSON API endpoint for algorithm parameters and their values.

    Returns parameters with nested values for a given inventory algorithm.
    Used by the configuration form to dynamically render parameter fields.
    """

    def get(self, request, algorithm_pk):
        from .serializers import InventoryAlgorithmParameterSerializer

        try:
            algorithm = InventoryAlgorithm.objects.get(pk=algorithm_pk)
        except InventoryAlgorithm.DoesNotExist:
            return Response({"error": "Algorithm not found"}, status=404)

        parameters = InventoryAlgorithmParameter.objects.filter(
            inventory_algorithm=algorithm
        ).prefetch_related("inventoryalgorithmparametervalue_set")

        scenario_id = request.query_params.get("scenario")
        if not (
            scenario_id
            and scenario_id.isascii()
            and scenario_id.isdigit()
            and filter_queryset_for_user(Scenario.objects.all(), request.user)
            .filter(pk=scenario_id)
            .exists()
        ):
            scenario_id = None

        serializer = InventoryAlgorithmParameterSerializer(
            parameters,
            many=True,
            context={"scenario_id": scenario_id},
        )
        return Response(serializer.data)


@login_required
def download_scenario_summary(request, scenario_pk):
    scenario = get_object_or_404(
        filter_queryset_for_user(Scenario.objects.all(), request.user),
        pk=scenario_pk,
    )
    if not decide(request.user, "export", scenario).allowed:
        return HttpResponseForbidden()
    file_name = f"scenario_{scenario_pk}_summary.json"
    with io.StringIO(json.dumps(scenario.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type="application/json")
        response["Content-Disposition"] = f"attachment; filename={file_name}"
        return response


def get_visible_result_layer(user, layer_name):
    """Return the live result layer of a scenario the user may read, else 404."""
    visible_scenarios = filter_queryset_for_user(Scenario.objects.all(), user)
    return get_object_or_404(
        Layer.objects.select_related("scenario"),
        table_name=layer_name,
        scenario__in=visible_scenarios,
    )


def result_layer_version(layer):
    """Fingerprint of the layer's feature rows and aggregates.

    Recomputations replace the rows of the result table, so hashing their
    content changes the token whenever any result value or geometry changes.
    """
    table = connection.ops.quote_name(layer.get_feature_collection()._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t.id), '')) "  # noqa: S608
            f"FROM {table} t"
        )
        features_digest = cursor.fetchone()[0]
    aggregates = list(
        layer.layeraggregatedvalue_set.order_by("pk").values_list(
            "pk", "name", "value", "unit"
        )
    )
    payload = json.dumps([layer.pk, features_digest, aggregates], default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def mark_private_result_uncacheable(response, layer):
    """Keep layers of unpublished scenarios out of browser caches."""
    if layer.scenario.publication_status != Scenario.STATUS_PUBLISHED:
        response["Cache-Control"] = "private, no-store"
    return response


class ResultLayerGeoJSONAPI(APIView):
    """GeoJSON feature collection of a scenario result layer for Leaflet maps."""

    permission_classes = (AllowAny,)

    def get(self, request, layer_name):
        layer = get_visible_result_layer(request.user, layer_name)
        feature_collection = layer.get_feature_collection()
        meta = type(
            "Meta", (BaseResultMapSerializer.Meta,), {"model": feature_collection}
        )
        serializer_class = type(
            "ResultLayerSerializer", (BaseResultMapSerializer,), {"Meta": meta}
        )
        serializer = serializer_class(feature_collection.objects.all(), many=True)
        response = Response(serializer.data)
        response["X-Data-Version"] = result_layer_version(layer)
        return mark_private_result_uncacheable(response, layer)


class ResultLayerVersionAPI(APIView):
    """Version token used by maps.js to revalidate cached result geometries."""

    permission_classes = (AllowAny,)

    def get(self, request, layer_name):
        layer = get_visible_result_layer(request.user, layer_name)
        response = Response({"version": result_layer_version(layer)})
        return mark_private_result_uncacheable(response, layer)


class ScenarioResultView(ScenarioMapMixin, UserCreatedObjectDetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = "scenario_result_detail.html"
    model = Scenario

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        result = ScenarioResult(scenario)
        context["result_layers"] = (
            result.layers.select_related(
                "feedstock", "algorithm__geodataset", "stream__geodataset"
            )
            .prefetch_related(
                Prefetch(
                    "layeraggregatedvalue_set",
                    queryset=LayerAggregatedValue.objects.order_by("pk"),
                )
            )
            .order_by("pk")
        )
        context["charts"] = result.get_charts()
        context.update(scenario_presentation_context(scenario, self.request.user))
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        if scenario.status == ScenarioStatus.Status.RUNNING:
            context = {
                "object": scenario,
                "scenario": scenario,
                "task_list": {"tasks": []},
                **scenario_presentation_context(scenario, request.user),
            }
            for task in (
                RunningTask.objects.filter(scenario=scenario)
                .exclude(algorithm__isnull=True, stream__isnull=True)
                .select_related("algorithm", "stream__material")
            ):
                context["task_list"]["tasks"].append(
                    {
                        "task_id": task.uuid,
                        "algorithm_name": task.algorithm.name
                        if task.algorithm_id
                        else str(task.stream),
                    }
                )

            return render(request, "evaluation_progress.html", context)
        if scenario.status == ScenarioStatus.Status.FAILED:
            return render(
                request,
                "evaluation_failed.html",
                {
                    "object": scenario,
                    "scenario": scenario,
                    **scenario_presentation_context(scenario, request.user),
                },
            )
        context = self.get_context_data()
        return self.render_to_response(context)


class ScenarioEvaluationProgressView(RedirectView):
    """The result page shows the progress, failure or results of a scenario."""

    pattern_name = "scenario-result"


@method_decorator(never_cache, name="dispatch")
class ScenarioEvaluationStatusView(UserCreatedObjectDetailView):
    """Whether a scenario is still evaluating, and the Celery state of each algorithm."""

    model = Scenario

    def get(self, request, *args, **kwargs):
        scenario = self.get_object()
        tasks = RunningTask.objects.filter(scenario=scenario).exclude(
            algorithm__isnull=True, stream__isnull=True
        )
        return JsonResponse(
            {
                "running": scenario.status == ScenarioStatus.Status.RUNNING,
                "tasks": {
                    str(task.uuid): AsyncResult(str(task.uuid)).status for task in tasks
                },
            }
        )


class ScenarioResultDetailMapView(MapMixin, DetailView):
    """View of an individual result map in large size"""

    model = Layer
    context_object_name = "layer"
    template_name = "result_detail_map.html"

    def get_object(self, **kwargs):
        visible_scenarios = filter_queryset_for_user(
            Scenario.objects.all(), self.request.user
        )
        scenario = get_object_or_404(visible_scenarios, id=self.kwargs.get("pk"))
        algorithm = get_object_or_404(
            InventoryAlgorithm, id=self.kwargs.get("algorithm_pk")
        )
        feedstock = get_object_or_404(Material, id=self.kwargs.get("feedstock_pk"))
        return get_object_or_404(
            Layer.objects.select_related(
                "scenario", "algorithm__geodataset", "stream__geodataset"
            ),
            scenario=scenario,
            algorithm=algorithm,
            feedstock=feedstock,
        )

    def get_region_feature_id(self):
        return self.object.scenario.region_id

    def get_catchment_feature_id(self):
        return self.object.scenario.catchment_id

    def get_features_feature_id(self):
        return None

    def get_features_geometries_url(self):
        return reverse(
            "data-result-layer", kwargs={"layer_name": self.object.table_name}
        )

    def get_override_params(self):
        params = super().get_override_params()
        params["load_features"] = True
        params["features_layer_details_url_template"] = ""
        params["features_layer_summary_url"] = ""
        return params

    def get_map_title(self):
        return f"{self.object.scenario.name}: {self.object.source_label}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object.scenario
        context.update(
            build_breadcrumb_context(
                module_label="Inventories",
                module_url=reverse("inventories-explorer"),
                section_label="Scenarios",
                section_url=reverse("scenario-list"),
                object_label=scenario.name,
                object_url=reverse("scenario-result", kwargs={"pk": scenario.pk}),
                action_label="Result map",
                page_title=self.get_map_title(),
            )
        )
        return context


class ScenarioResultLayerMapView(ScenarioResultDetailMapView):
    """Result map of one layer, addressed by the layer itself."""

    def get_object(self, **kwargs):
        visible_scenarios = filter_queryset_for_user(
            Scenario.objects.all(), self.request.user
        )
        scenario = get_object_or_404(visible_scenarios, id=self.kwargs.get("pk"))
        return get_object_or_404(
            Layer.objects.select_related(
                "scenario", "algorithm__geodataset", "stream__geodataset"
            ),
            scenario=scenario,
            pk=self.kwargs.get("layer_pk"),
        )


@login_required
def download_scenario_result_summary(request, scenario_pk):
    scenario = get_object_or_404(
        filter_queryset_for_user(Scenario.objects.all(), request.user),
        pk=scenario_pk,
    )
    if not decide(request.user, "export", scenario).allowed:
        return HttpResponseForbidden()
    result = ScenarioResult(scenario)
    with io.StringIO(json.dumps(result.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type="application/json")
        response["Content-Disposition"] = (
            f"attachment; filename=scenario_{scenario_pk}_result_summary.json"
        )
        return response
