import hashlib
import io
import json
import re

from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import connection, transaction
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
    CreateView,
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
from utils.object_management.permissions import (
    filter_queryset_for_user,
    get_object_policy,
)
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

from .evaluations import ScenarioResult
from .exceptions import InvalidParameterValue
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
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
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


class SeasonalDistributionCreateView(LoginRequiredMixin, CreateView):
    form_class = SeasonalDistributionModelForm
    template_name = "seasonal_distribution_create.html"
    success_url = "/inventories/materials/{material_id}"


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
    dashboard_url = reverse_lazy("inventories-explorer")


class PrivateScenarioFilterView(PrivateObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet
    dashboard_url = reverse_lazy("inventories-explorer")


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


class ScenarioDetailView(MapMixin, UserCreatedObjectDetailView):
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
        context["allow_edit"] = self.allow_edit
        context.update(scenario_presentation_context(self.object, request.user))
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        if (
            not request.user.is_authenticated
            or not get_object_policy(request.user, scenario, request=request)[
                "can_edit"
            ]
        ):
            return HttpResponseForbidden()
        start_inventory_run(scenario.id)
        return redirect("scenario-result", scenario.id)


class ScenarioUpdateView(UserCreatedObjectUpdateView):
    model = Scenario
    form_class = ScenarioModelForm


class ScenarioModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Scenario


# ----------- Scenario Utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Scenario


CUSTOM_PARAMETER_VALUE = "custom"

KWARG_NAME_PATTERN = re.compile(r"^\w{1,28}$")


def _parse_kwarg_rows(request):
    """Parse the free-form factor rows of the generic add-inventory form.

    Expects aligned ``kwarg_name``/``kwarg_value`` lists; optional
    ``kwarg_unit``/``kwarg_standard_deviation``/``kwarg_preset`` lists are
    padded. Returns ``[{"name", "value", "unit", "standard_deviation",
    "preset"}]`` dicts — ``preset`` holds an existing
    InventoryAlgorithmParameterValue id when the row was filled from a preset.
    """
    names = request.POST.getlist("kwarg_name")
    raw_values = request.POST.getlist("kwarg_value")
    if len(names) != len(raw_values):
        raise InvalidParameterValue("Incomplete factor row.")
    # Optional lists may be shorter — pad them.
    units = request.POST.getlist("kwarg_unit")
    raw_stds = request.POST.getlist("kwarg_standard_deviation")
    raw_presets = request.POST.getlist("kwarg_preset")
    units += [""] * (len(names) - len(units))
    raw_stds += [""] * (len(names) - len(raw_stds))
    raw_presets += [""] * (len(names) - len(raw_presets))
    specs = []
    for name, raw_value, unit, raw_std, raw_preset in zip(
        names, raw_values, units, raw_stds, raw_presets, strict=False
    ):
        name = name.strip()
        if not KWARG_NAME_PATTERN.match(name):
            raise InvalidParameterValue(
                f"Invalid parameter name '{name}'. Use letters, digits and "
                "underscores only (max 28 characters)."
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
        if len(unit) > 20:
            raise InvalidParameterValue(
                f"The unit for parameter '{name}' is too long (max 20 characters)."
            )
        preset = None
        if raw_preset not in (None, ""):
            try:
                preset = int(raw_preset)
            except ValueError:
                raise InvalidParameterValue("Invalid preset reference.") from None
        specs.append(
            {
                "name": name,
                "value": value,
                "unit": unit.strip(),
                "standard_deviation": std,
                "preset": preset,
            }
        )
    return specs


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


class ScenarioAddInventoryAlgorithmView(
    LoginRequiredMixin, UserPassesTestMixin, TemplateResponseMixin, ModelFormMixin, View
):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationAddForm
    template_name = "scenario_configuration_add.html"
    object = None

    def test_func(self):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("pk"))
        policy = get_object_policy(self.request.user, scenario, request=self.request)
        return policy["can_edit"]

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
            return self._post_generic(request, scenario, ref)
        feedstock = _get_posted_object_or_404(Material, request.POST.get("feedstock"))
        algorithm = _get_posted_object_or_404(InventoryAlgorithm, ref or None)
        if (
            not filter_queryset_for_user(GeoDataset.objects.all(), request.user)
            .filter(pk=algorithm.geodataset_id)
            .exists()
        ):
            raise Http404
        try:
            sample_series = _posted_sample_series(request, feedstock)
            with transaction.atomic():
                values = resolve_parameter_values(request, algorithm, scenario)
                scenario.add_inventory_algorithm(
                    feedstock, algorithm, values, sample_series=sample_series
                )
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        except FeedstockNotImplemented:
            raise Http404 from None
        return redirect("scenario-detail", pk=scenario.pk)

    def _post_generic(self, request, scenario, function_name):
        """Materialize a generic algorithm for the chosen dataset and apply
        the free-form factor rows posted with the form."""
        from .algorithms import (
            GENERIC_FUNCTION_LABELS,
            RESERVED_ALGORITHM_KWARGS,
            InventoryAlgorithms,
        )

        if function_name not in GENERIC_FUNCTION_LABELS:
            return HttpResponseBadRequest("Unknown generic function.")
        geodataset = _get_posted_object_or_404(
            GeoDataset,
            request.POST.get("geodataset"),
            queryset=filter_queryset_for_user(GeoDataset.objects.all(), request.user),
        )
        if geodataset.region_id != scenario.region_id:
            return HttpResponseBadRequest(
                "The geodataset does not belong to the scenario region."
            )
        if function_name not in InventoryAlgorithms.generic_functions(geodataset):
            return HttpResponseBadRequest(
                f"'{function_name}' does not apply to this dataset's geometry."
            )
        feedstock = _get_posted_object_or_404(Material, request.POST.get("feedstock"))
        try:
            sample_series = _posted_sample_series(request, feedstock)
            kwarg_specs = _parse_kwarg_rows(request)
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        for spec in kwarg_specs:
            if spec["name"] in RESERVED_ALGORITHM_KWARGS:
                return HttpResponseBadRequest(
                    f"'{spec['name']}' is a reserved parameter name."
                )

        # Optional feature filter ("column=value") restricts the inventory to a
        # subset of features — e.g. one crop out of many in a parcels dataset.
        filter_column = request.POST.get("filter_column", "").strip()
        filter_value = request.POST.get("filter_value", "").strip()
        filter_spec = None
        if filter_column or filter_value:
            if not (filter_column and filter_value):
                return HttpResponseBadRequest(
                    "Both a filter column and a filter value are required."
                )
            valid_columns = {
                c["name"] for c in InventoryAlgorithms.feature_columns(geodataset)
            }
            if filter_column not in valid_columns:
                return HttpResponseBadRequest(
                    f"'{filter_column}' is not a filterable column of this dataset."
                )
            filter_spec = f"{filter_column}={filter_value}"
            if len(filter_spec) > 56:
                return HttpResponseBadRequest("The feature filter is too long.")

        try:
            with transaction.atomic():
                self._apply_generic_post(
                    scenario,
                    function_name,
                    geodataset,
                    filter_spec,
                    kwarg_specs,
                    feedstock,
                    sample_series,
                )
        except InvalidParameterValue as exc:
            return HttpResponseBadRequest(str(exc))
        except FeedstockNotImplemented:
            raise Http404 from None
        return redirect("scenario-detail", pk=scenario.pk)

    def _apply_generic_post(
        self,
        scenario,
        function_name,
        geodataset,
        filter_spec,
        kwarg_specs,
        feedstock,
        sample_series,
    ):
        """Materialize the generic algorithm and store its configuration.

        Runs inside a transaction — InvalidParameterValue aborts the whole
        write so a rejected request leaves no partial parameter rows.
        """
        from .algorithms import GENERIC_FUNCTION_LABELS, GENERIC_MODULE_PATH

        algorithm, _created = InventoryAlgorithm.objects.get_or_create(
            source_module=GENERIC_MODULE_PATH,
            function_name=function_name,
            geodataset=geodataset,
            defaults={"name": GENERIC_FUNCTION_LABELS[function_name]},
        )
        algorithm.feedstocks.add(feedstock)
        values = {}
        if filter_spec:
            parameter = InventoryAlgorithmParameter.objects.filter(
                inventory_algorithm=algorithm, short_name="feature_filter"
            ).first()
            if parameter is None:
                parameter = InventoryAlgorithmParameter.objects.create(
                    descriptive_name="Feature filter",
                    short_name="feature_filter",
                )
                parameter.inventory_algorithm.add(algorithm)
            values[parameter] = [
                InventoryAlgorithmParameterValue.objects.create(
                    name=filter_spec,
                    parameter=parameter,
                    value=1.0,
                    type=InventoryAlgorithmParameterValue.ValueType.SELECTION,
                    source="User selection",
                    is_custom=True,
                )
            ]
        for spec in kwarg_specs:
            parameter = InventoryAlgorithmParameter.objects.filter(
                inventory_algorithm=algorithm, short_name=spec["name"]
            ).first()
            if parameter is None:
                parameter = InventoryAlgorithmParameter.objects.create(
                    descriptive_name=spec["name"],
                    short_name=spec["name"],
                    unit=spec["unit"] or None,
                )
                parameter.inventory_algorithm.add(algorithm)
            elif spec["unit"] and parameter.unit and parameter.unit != spec["unit"]:
                # The parameter is shared by every configuration of this
                # algorithm — mutating its unit would reinterpret the
                # magnitudes of existing values.
                raise InvalidParameterValue(
                    f"Unit '{spec['unit']}' conflicts with the existing unit "
                    f"'{parameter.unit}' of parameter '{spec['name']}'."
                )
            elif spec["unit"] and not parameter.unit:
                parameter.unit = spec["unit"]
                parameter.save(update_fields=["unit"])
            if spec["preset"] is not None:
                preset = InventoryAlgorithmParameterValue.objects.filter(
                    pk=spec["preset"], parameter=parameter
                ).first()
                scenario_customs = set(
                    ScenarioInventoryConfiguration.objects.filter(
                        scenario=scenario, inventory_parameter=parameter
                    ).values_list("inventory_value_id", flat=True)
                )
                if preset is None or (
                    preset.is_custom and preset.id not in scenario_customs
                ):
                    raise InvalidParameterValue(
                        f"Invalid preset value for parameter '{spec['name']}'."
                    )
                values[parameter] = [preset]
                continue
            values[parameter] = [
                InventoryAlgorithmParameterValue.objects.create(
                    name="",
                    parameter=parameter,
                    value=spec["value"],
                    standard_deviation=spec["standard_deviation"],
                    source="User assumption",
                    is_custom=True,
                )
            ]
        scenario.add_inventory_algorithm(
            feedstock, algorithm, values, sample_series=sample_series
        )

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
    LoginRequiredMixin, UserPassesTestMixin, TemplateResponseMixin, ModelFormMixin, View
):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationUpdateForm
    template_name = "scenario_configuration_update.html"
    object = None

    def test_func(self):
        scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        policy = get_object_policy(self.request.user, scenario, request=self.request)
        return policy["can_edit"]

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
            with transaction.atomic():
                values = resolve_parameter_values(request, new_algorithm, scenario)
                scenario.remove_inventory_algorithm(
                    current_algorithm, current_feedstock
                )
                scenario.add_inventory_algorithm(
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
    LoginRequiredMixin, UserPassesTestMixin, View
):
    scenario = None
    algorithm = None
    feedstock = None

    def test_func(self):
        self.scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        policy = get_object_policy(
            self.request.user, self.scenario, request=self.request
        )
        return policy["can_edit"]

    def get(self, request, *args, **kwargs):
        self.scenario = get_object_or_404(Scenario, id=self.kwargs.get("scenario_pk"))
        self.algorithm = get_object_or_404(
            InventoryAlgorithm, id=self.kwargs.get("algorithm_pk")
        )
        self.feedstock = get_object_or_404(Material, id=self.kwargs.get("feedstock_pk"))
        self.scenario.remove_inventory_algorithm(
            algorithm=self.algorithm, feedstock=self.feedstock
        )
        return redirect("scenario-detail", pk=self.scenario.id)


class ScenarioGeoDataSetAutocompleteView(GeoDataSetAutocompleteView):
    """GeoDataset autocomplete scoped to a scenario's region.

    The widget passes the scenario id via either ``filter_by`` or
    ``exclude_by`` and an optional feedstock id via ``filter_by``. With a
    feedstock, datasets already configured for that feedstock's material in
    the scenario are excluded. Without one, every dataset in the region is
    offered — generic algorithms work on any dataset.
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

        queryset = queryset.filter(region=scenario.region)

        if feedstock_id:
            try:
                feedstock = Material.objects.get(pk=feedstock_id)
            except Material.DoesNotExist:
                return GeoDataset.objects.none()
            from django.db.models import Exists, OuterRef

            evaluated_q = ScenarioInventoryConfiguration.objects.filter(
                geodataset=OuterRef("pk"),
                scenario=scenario,
                feedstock=feedstock,
            )
            queryset = queryset.annotate(already_evaluated=Exists(evaluated_q)).filter(
                already_evaluated=False
            )

        return queryset


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


class GeoDatasetFunctionsAPIView(LoginRequiredMixin, APIView):
    """JSON endpoint listing the inventory functions applicable to a
    GeoDataset: the generic functions matching its geometry family plus any
    algorithms already registered on the dataset."""

    def get(self, request, geodataset_pk):
        from .algorithms import (
            GENERIC_FUNCTION_LABELS,
            GENERIC_MODULE_PATH,
            RESERVED_ALGORITHM_KWARGS,
            InventoryAlgorithms,
        )
        from .serializers import InventoryAlgorithmParameterSerializer

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

        functions = []
        for function_name in InventoryAlgorithms.generic_functions(geodataset):
            entry = {
                "function_name": function_name,
                "name": GENERIC_FUNCTION_LABELS[function_name],
                "parameters": [],
            }
            # If the generic algorithm has been materialized for this dataset
            # before, its parameters and their curated/scenario values are
            # offered as presets in the factor editor.
            algorithm = InventoryAlgorithm.objects.filter(
                source_module=GENERIC_MODULE_PATH,
                function_name=function_name,
                geodataset=geodataset,
            ).first()
            if algorithm is not None:
                parameters = algorithm.inventoryalgorithmparameter_set.exclude(
                    short_name__in=RESERVED_ALGORITHM_KWARGS
                )
                entry["parameters"] = InventoryAlgorithmParameterSerializer(
                    parameters,
                    many=True,
                    context={"scenario_id": scenario_id},
                ).data
            functions.append(entry)

        algorithms = InventoryAlgorithm.objects.filter(geodataset=geodataset)
        feedstock_id = request.query_params.get("feedstock")
        if feedstock_id:
            try:
                feedstock = Material.objects.get(pk=feedstock_id)
                algorithms = algorithms.filter(feedstocks=feedstock)
            except Material.DoesNotExist:
                algorithms = algorithms.none()
        try:
            columns = InventoryAlgorithms.feature_columns(geodataset)
        except Exception:
            columns = []
        return Response(
            {
                "geometry_family": InventoryAlgorithms.geometry_family(geodataset),
                "functions": functions,
                "algorithms": [
                    {"id": algorithm.pk, "name": str(algorithm)}
                    for algorithm in algorithms.order_by("name").distinct()
                ],
                "columns": columns,
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
    try:
        scenario = Scenario.objects.get(id=scenario_pk)
    except Scenario.DoesNotExist:
        raise Http404 from None
    policy = get_object_policy(request.user, scenario, request=request)
    if not (
        policy["is_owner"]
        or policy["is_published"]
        or policy["is_staff"]
        or policy["is_moderator"]
    ):
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


class ScenarioResultView(MapMixin, UserCreatedObjectDetailView):
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
            result.layers.select_related("feedstock", "algorithm__geodataset")
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
            for task in RunningTask.objects.filter(
                scenario=scenario, algorithm__isnull=False
            ).select_related("algorithm"):
                context["task_list"]["tasks"].append(
                    {
                        "task_id": task.uuid,
                        "algorithm_name": task.algorithm.name,
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
        tasks = RunningTask.objects.filter(scenario=scenario, algorithm__isnull=False)
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
            Layer.objects.select_related("scenario", "algorithm__geodataset"),
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
        return f"{self.object.scenario.name}: {self.object.algorithm.geodataset.name}"

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


@login_required
def download_scenario_result_summary(request, scenario_pk):
    try:
        scenario = Scenario.objects.get(id=scenario_pk)
    except Scenario.DoesNotExist:
        raise Http404 from None
    policy = get_object_policy(request.user, scenario, request=request)
    if not (
        policy["is_owner"]
        or policy["is_published"]
        or policy["is_staff"]
        or policy["is_moderator"]
    ):
        return HttpResponseForbidden()
    result = ScenarioResult(scenario)
    with io.StringIO(json.dumps(result.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type="application/json")
        response["Content-Disposition"] = (
            f"attachment; filename=scenario_{scenario_pk}_result_summary.json"
        )
        return response
