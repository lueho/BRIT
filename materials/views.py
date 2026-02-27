from collections import Counter, defaultdict
from decimal import Decimal

from bootstrap_modal_forms.generic import BSModalFormView, BSModalUpdateView
from crispy_forms.helper import FormHelper
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, RedirectView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from extra_views import UpdateWithInlinesView

from distributions.models import TemporalDistribution
from distributions.plots import DoughnutChart
from utils.file_export.views import SingleObjectFileExportView
from utils.object_management.permissions import get_object_policy
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    ReviewObjectFilterView,
    ReviewObjectListView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    UserCreatedObjectUpdateWithInlinesView,
    UserOwnsObjectMixin,
)
from utils.properties.models import Unit
from utils.properties.units import UnitConversionError
from utils.views import NextOrSuccessUrlMixin

from .filters import (
    AnalyticalMethodListFilter,
    MaterialCategoryListFilter,
    MaterialComponentGroupListFilter,
    MaterialComponentListFilter,
    MaterialListFilter,
    MaterialPropertyListFilter,
    SampleFilter,
    SampleSeriesFilter,
)
from .forms import (
    AddComponentModalForm,
    AddCompositionModalForm,
    AddLiteratureSourceForm,
    AddSeasonalVariationForm,
    AnalyticalMethodModelForm,
    ComponentGroupModalModelForm,
    ComponentGroupModelForm,
    ComponentModalModelForm,
    ComponentModelForm,
    ComponentShareDistributionFormSetHelper,
    Composition,
    CompositionModalModelForm,
    CompositionModelForm,
    InlineWeightShare,
    MaterialCategoryModalModelForm,
    MaterialCategoryModelForm,
    MaterialModalModelForm,
    MaterialModelForm,
    MaterialPropertyModalModelForm,
    MaterialPropertyModelForm,
    MaterialPropertyValueModalModelForm,
    MaterialPropertyValueModelForm,
    ModalInlineComponentShare,
    SampleAddCompositionForm,
    SampleModalModelForm,
    SampleModelForm,
    SampleSeriesAddTemporalDistributionModalModelForm,
    SampleSeriesModalModelForm,
    SampleSeriesModelForm,
    WeightShareUpdateFormSetHelper,
)
from .models import (
    AnalyticalMethod,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
    WeightShare,
    get_or_create_sample_substrate_category,
)
from .serializers import (
    CompositionDoughnutChartSerializer,
    CompositionModelSerializer,
    SampleModelSerializer,
    SampleSeriesModelSerializer,
)


class MaterialsExplorerView(TemplateView):
    template_name = "materials_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["material_count"] = Material.objects.filter(
            type="material", publication_status="published"
        ).count()
        context["category_count"] = MaterialCategory.objects.filter(
            publication_status="published"
        ).count()
        context["sample_count"] = Sample.objects.filter(
            publication_status="published"
        ).count()
        context["series_count"] = SampleSeries.objects.filter(
            publication_status="published"
        ).count()
        context["method_count"] = AnalyticalMethod.objects.filter(
            publication_status="published"
        ).count()
        context["component_count"] = MaterialComponent.objects.filter(
            publication_status="published"
        ).count()
        context["group_count"] = MaterialComponentGroup.objects.filter(
            publication_status="published"
        ).count()
        context["property_count"] = MaterialProperty.objects.filter(
            publication_status="published"
        ).count()
        return context


class MaterialsDiagramView(TemplateView):
    template_name = "materials_diagram.html"


# ----------- Material Category CRUD ----------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------


class MaterialCategoryPublishedListView(PublishedObjectFilterView):
    model = MaterialCategory
    filterset_class = MaterialCategoryListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialCategoryPrivateListView(PrivateObjectFilterView):
    model = MaterialCategory
    filterset_class = MaterialCategoryListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialCategoryReviewListView(ReviewObjectListView):
    model = MaterialCategory
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialCategoryCreateView(UserCreatedObjectCreateView):
    form_class = MaterialCategoryModelForm
    permission_required = "materials.add_materialcategory"


class MaterialCategoryModalCreateView(UserCreatedObjectModalCreateView):
    form_class = MaterialCategoryModalModelForm
    permission_required = "materials.add_materialcategory"


class MaterialCategoryDetailView(UserCreatedObjectDetailView):
    model = MaterialCategory


class MaterialCategoryModalDetailView(UserCreatedObjectModalDetailView):
    template_name = "modal_detail.html"
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryUpdateView(UserCreatedObjectUpdateView):
    model = MaterialCategory
    form_class = MaterialCategoryModelForm


class MaterialCategoryModalUpdateView(UserCreatedObjectModalUpdateView):
    model = MaterialCategory
    form_class = MaterialCategoryModalModelForm


class MaterialCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialCategory


class MaterialCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    model = MaterialCategory


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPublishedListView(PublishedObjectFilterView):
    model = Material
    queryset = Material.objects.filter(type="material")
    filterset_class = MaterialListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialPrivateListView(PrivateObjectFilterView):
    model = Material
    queryset = Material.objects.filter(type="material")
    filterset_class = MaterialListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialReviewListView(ReviewObjectListView):
    model = Material
    queryset = Material.objects.filter(type="material")
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialCreateView(UserCreatedObjectCreateView):
    form_class = MaterialModelForm
    permission_required = "materials.add_material"


class MaterialModalCreateView(UserCreatedObjectModalCreateView):
    form_class = MaterialModalModelForm
    permission_required = "materials.add_material"


class MaterialDetailView(UserCreatedObjectDetailView):
    model = Material


class MaterialModalDetailView(UserCreatedObjectModalDetailView):
    model = Material


class MaterialUpdateView(UserCreatedObjectUpdateView):
    model = Material
    form_class = MaterialModelForm


class MaterialModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Material
    form_class = MaterialModalModelForm


class MaterialModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Material


# ----------- Material Utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Material


class SampleSubstrateMaterialAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete for sample substrate materials restricted to substrate category."""

    model = Material

    def get_queryset(self):
        queryset = super().get_queryset()
        substrate_category, _ = get_or_create_sample_substrate_category()
        return queryset.filter(
            type="material",
            categories=substrate_category,
        ).distinct()


# ----------- Material Component CRUD ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentPublishedListView(PublishedObjectFilterView):
    model = MaterialComponent
    filterset_class = MaterialComponentListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class ComponentPrivateListView(PrivateObjectFilterView):
    model = MaterialComponent
    filterset_class = MaterialComponentListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class ComponentReviewListView(ReviewObjectListView):
    model = MaterialComponent
    dashboard_url = reverse_lazy("materials-explorer")


class ComponentCreateView(UserCreatedObjectCreateView):
    form_class = ComponentModelForm
    permission_required = "materials.add_materialcomponent"


class ComponentModalCreateView(UserCreatedObjectModalCreateView):
    form_class = ComponentModalModelForm
    permission_required = "materials.add_materialcomponent"


class ComponentDetailView(UserCreatedObjectDetailView):
    model = MaterialComponent


class ComponentModalDetailView(UserCreatedObjectModalDetailView):
    model = MaterialComponent


class ComponentUpdateView(UserCreatedObjectUpdateView):
    model = MaterialComponent
    form_class = ComponentModelForm


class ComponentModalUpdateView(UserCreatedObjectModalUpdateView):
    model = MaterialComponent
    form_class = ComponentModalModelForm


class ComponentModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialComponent


# ----------- Material Component Utils ---------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentAutocompleteView(UserCreatedObjectAutocompleteView):
    model = MaterialComponent


# ----------- Material Component Groups CRUD----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialComponentGroupPublishedListView(PublishedObjectFilterView):
    model = MaterialComponentGroup
    filterset_class = MaterialComponentGroupListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialComponentGroupPrivateListView(PrivateObjectFilterView):
    model = MaterialComponentGroup
    filterset_class = MaterialComponentGroupListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialComponentGroupReviewListView(ReviewObjectListView):
    model = MaterialComponentGroup
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialComponentGroupCreateView(UserCreatedObjectCreateView):
    form_class = ComponentGroupModelForm
    permission_required = "materials.add_materialcomponentgroup"


class MaterialComponentGroupModalCreateView(UserCreatedObjectModalCreateView):
    form_class = ComponentGroupModalModelForm
    permission_required = "materials.add_materialcomponentgroup"


class MaterialComponentGroupDetailView(UserCreatedObjectDetailView):
    model = MaterialComponentGroup


class MaterialComponentGroupModalDetailView(UserCreatedObjectModalDetailView):
    model = MaterialComponentGroup


class MaterialComponentGroupUpdateView(UserCreatedObjectUpdateView):
    model = MaterialComponentGroup
    form_class = ComponentGroupModelForm


class MaterialComponentGroupModalUpdateView(UserCreatedObjectModalUpdateView):
    model = MaterialComponentGroup
    form_class = ComponentGroupModalModelForm


class MaterialComponentGroupModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialComponentGroup


class MaterialComponentGroupAutocompleteView(UserCreatedObjectAutocompleteView):
    model = MaterialComponentGroup


# ----------- Material Property CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyPublishedListView(PublishedObjectFilterView):
    model = MaterialProperty
    filterset_class = MaterialPropertyListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialPropertyPrivateListView(PrivateObjectFilterView):
    model = MaterialProperty
    filterset_class = MaterialPropertyListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialPropertyReviewListView(ReviewObjectListView):
    model = MaterialProperty
    dashboard_url = reverse_lazy("materials-explorer")


class MaterialPropertyCreateView(UserCreatedObjectCreateView):
    form_class = MaterialPropertyModelForm
    permission_required = "materials.add_materialproperty"


class MaterialPropertyModalCreateView(UserCreatedObjectModalCreateView):
    form_class = MaterialPropertyModalModelForm
    permission_required = "materials.add_materialproperty"


class MaterialPropertyDetailView(UserCreatedObjectDetailView):
    model = MaterialProperty


class MaterialPropertyModalDetailView(UserCreatedObjectModalDetailView):
    model = MaterialProperty


class MaterialPropertyUpdateView(UserCreatedObjectUpdateView):
    model = MaterialProperty
    form_class = MaterialPropertyModelForm


class MaterialPropertyModalUpdateView(UserCreatedObjectModalUpdateView):
    model = MaterialProperty
    form_class = MaterialPropertyModalModelForm


class MaterialPropertyModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialProperty


class MaterialPropertyAutocompleteView(UserCreatedObjectAutocompleteView):
    model = MaterialProperty


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyValueModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialPropertyValue

    def get_success_url(self):
        return reverse(
            "sample-detail", kwargs={"pk": self.object.sample_set.first().pk}
        )


# ----------- Analytical Method CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AnalyticalMethodPublishedListView(PublishedObjectFilterView):
    model = AnalyticalMethod
    filterset_class = AnalyticalMethodListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class AnalyticalMethodPrivateListView(PrivateObjectFilterView):
    model = AnalyticalMethod
    filterset_class = AnalyticalMethodListFilter
    dashboard_url = reverse_lazy("materials-explorer")


class AnalyticalMethodReviewListView(ReviewObjectListView):
    model = AnalyticalMethod
    dashboard_url = reverse_lazy("materials-explorer")


class AnalyticalMethodCreateView(UserCreatedObjectCreateView):
    form_class = AnalyticalMethodModelForm
    permission_required = "materials.add_analyticalmethod"


class AnalyticalMethodDetailView(UserCreatedObjectDetailView):
    model = AnalyticalMethod


class AnalyticalMethodModalDetailView(UserCreatedObjectModalDetailView):
    model = AnalyticalMethod


class AnalyticalMethodUpdateView(UserCreatedObjectUpdateView):
    model = AnalyticalMethod
    form_class = AnalyticalMethodModelForm


class AnalyticalMethodModalDeleteView(UserCreatedObjectModalDeleteView):
    model = AnalyticalMethod


class AnalyticalMethodAutocompleteView(UserCreatedObjectAutocompleteView):
    model = AnalyticalMethod


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesPublishedListView(PublishedObjectFilterView):
    model = SampleSeries
    filterset_class = SampleSeriesFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SampleSeriesPrivateListView(PrivateObjectFilterView):
    model = SampleSeries
    filterset_class = SampleSeriesFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SampleSeriesReviewListView(ReviewObjectFilterView):
    model = SampleSeries
    filterset_class = SampleSeriesFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SampleSeriesCreateView(UserCreatedObjectCreateView):
    form_class = SampleSeriesModelForm
    permission_required = "materials.add_sampleseries"


class SampleSeriesModalCreateView(UserCreatedObjectModalCreateView):
    form_class = SampleSeriesModalModelForm
    permission_required = "materials.add_sampleseries"


class SampleSeriesDetailView(UserCreatedObjectDetailView):
    model = SampleSeries

    def get_context_data(self, **kwargs):
        kwargs["data"] = SampleSeriesModelSerializer(self.object).data
        return super().get_context_data(**kwargs)


class SampleSeriesModalDetailView(UserCreatedObjectModalDetailView):
    model = SampleSeries


class SampleSeriesUpdateView(UserCreatedObjectUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModelForm


class SampleSeriesModalUpdateView(UserCreatedObjectModalUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModalModelForm


class SampleSeriesModalDeleteView(UserCreatedObjectModalDeleteView):
    model = SampleSeries


# ----------- Sample Series Utils --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCreateDuplicateView(UserCreatedObjectUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModelForm
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(
            creator=self.request.user, **form.cleaned_data
        )
        return super().form_valid(form)


class SampleSeriesModalAddDistributionView(UserCreatedObjectModalUpdateView):
    model = SampleSeries
    form_class = SampleSeriesAddTemporalDistributionModalModelForm

    def form_valid(self, form):
        self.object.temporal_distributions.add(form.cleaned_data["distribution"])
        return HttpResponseRedirect(self.get_success_url())


class SampleSeriesAutoCompleteView(UserCreatedObjectAutocompleteView):
    model = SampleSeries


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SamplePublishedListView(PublishedObjectFilterView):
    model = Sample
    filterset_class = SampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SamplePrivateListView(PrivateObjectFilterView):
    model = Sample
    filterset_class = SampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SampleReviewListView(ReviewObjectFilterView):
    model = Sample
    filterset_class = SampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


class FeaturedSampleListView(PublishedObjectListView):
    template_name = "featured_sample_list.html"
    model = Sample
    queryset = Sample.objects.filter(series__publish=True)


class SampleCreateView(UserCreatedObjectCreateView):
    form_class = SampleModelForm
    permission_required = "materials.add_sample"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class SampleModalCreateView(UserCreatedObjectModalCreateView):
    form_class = SampleModalModelForm
    permission_required = "materials.add_sample"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class SampleDetailView(UserCreatedObjectDetailView):
    model = Sample

    @staticmethod
    def _normalize_unit_name(unit):
        return (getattr(unit, "name", "") or "").strip().lower().replace(" ", "")

    @staticmethod
    def _normalize_component_name(component):
        return (getattr(component, "name", "") or "").strip().lower().replace(" ", "")

    def _is_percent_of_dm_measurement(self, measurement):
        unit_name = self._normalize_unit_name(measurement.unit)
        basis_name = self._normalize_component_name(measurement.basis_component)
        return unit_name in {"%", "percent"} and basis_name in {"dm", "drymatter"}

    def _to_weight_percent(self, value, unit, percent_unit):
        if percent_unit is None:
            return None

        try:
            converted_value = unit.convert(value, percent_unit)
        except UnitConversionError:
            return None

        return Decimal(str(converted_value))

    def _build_persisted_composition_charts(self, compositions):
        charts = {}
        for composition in compositions:
            chart_data = CompositionDoughnutChartSerializer(composition).data
            chart = DoughnutChart(**chart_data)
            charts[f"composition-chart-{composition.id}"] = chart.as_dict()
        return charts

    def _build_derived_compositions(self, component_measurements):
        grouped_values = {}
        grouped_components = defaultdict(dict)
        group_is_dm_basis = defaultdict(lambda: True)
        group_basis_components = defaultdict(list)
        for measurement in component_measurements:
            average = Decimal(measurement.average)
            if average <= 0:
                continue

            grouped_values[measurement.group_id] = measurement.group
            if not self._is_percent_of_dm_measurement(measurement):
                group_is_dm_basis[measurement.group_id] = False
            if measurement.basis_component is not None:
                group_basis_components[measurement.group_id].append(
                    measurement.basis_component
                )
            component_map = grouped_components[measurement.group_id]
            component_map[measurement.component_id] = component_map.get(
                measurement.component_id,
                {
                    "component": measurement.component,
                    "measurements": [],
                },
            )
            component_map[measurement.component_id]["measurements"].append(measurement)

        if not grouped_values:
            return []

        other_component = MaterialComponent.objects.other()
        percent_unit = Unit.objects.filter(name="%").first() or Unit(
            name="%", symbol="percent"
        )
        compositions = []

        for group_id, group in sorted(
            grouped_values.items(), key=lambda item: item[1].name.lower()
        ):
            is_dm_basis = group_is_dm_basis[group_id]
            display_unit = "% of DM" if is_dm_basis else "%"
            basis_components = group_basis_components[group_id]
            if basis_components:
                basis_counts = Counter(component.pk for component in basis_components)
                reference_component_id = max(
                    basis_counts, key=lambda component_id: basis_counts[component_id]
                )
                reference_component = next(
                    component
                    for component in basis_components
                    if component.pk == reference_component_id
                )
            else:
                reference_component = MaterialComponent.objects.default()
            component_values = grouped_components[group_id]

            shares = []
            for component_data in component_values.values():
                component_percent = Decimal("0.0")
                for measurement in component_data["measurements"]:
                    measurement_value = Decimal(measurement.average)
                    if is_dm_basis:
                        component_percent += measurement_value
                    else:
                        converted = self._to_weight_percent(
                            measurement_value, measurement.unit, percent_unit
                        )
                        if converted is not None:
                            component_percent += converted

                if component_percent <= 0:
                    continue

                shares.append(
                    {
                        "component": component_data["component"].pk,
                        "component_name": component_data["component"].name,
                        "average": float(component_percent / Decimal("100")),
                        "standard_deviation": 0.0,
                        "as_percentage": f"{round(component_percent, 1)} ± 0.0{display_unit}",
                    }
                )

            if not shares:
                continue

            total_percent = sum(
                (Decimal(str(share["average"])) * Decimal("100") for share in shares),
                Decimal("0.0"),
            )
            if total_percent < Decimal("100"):
                other_gap = Decimal("100") - total_percent
                other_share = next(
                    (
                        share
                        for share in shares
                        if share["component"] == other_component.pk
                    ),
                    None,
                )
                if other_share is not None:
                    existing_percent = Decimal(str(other_share["average"])) * Decimal(
                        "100"
                    )
                    updated_percent = existing_percent + other_gap
                    other_share["average"] = float(updated_percent / Decimal("100"))
                    other_share["as_percentage"] = (
                        f"{round(updated_percent, 1)} ± 0.0{display_unit}"
                    )
                else:
                    shares.append(
                        {
                            "component": other_component.pk,
                            "component_name": other_component.name,
                            "average": float(other_gap / Decimal("100")),
                            "standard_deviation": 0.0,
                            "as_percentage": f"{round(other_gap, 1)} ± 0.0{display_unit}",
                        }
                    )

            shares.sort(
                key=lambda share: (
                    share["component"] == other_component.pk,
                    share["component_name"].lower(),
                )
            )

            compositions.append(
                {
                    "id": f"derived-{group_id}",
                    "group": group.pk,
                    "group_name": group.name,
                    "sample": self.object.pk,
                    "fractions_of": reference_component.pk,
                    "fractions_of_name": reference_component.name,
                    "shares": shares,
                    "is_derived": True,
                }
            )

        return compositions

    def _build_derived_composition_charts(self, compositions):
        charts = {}
        for composition in compositions:
            labels = [share["component_name"] for share in composition["shares"]]
            values = [share["average"] for share in composition["shares"]]
            chart = DoughnutChart(
                id=f"materialCompositionChart-{composition['id']}",
                title="Composition",
                unit="%",
                labels=labels,
                data=[{"label": "Fraction", "unit": "%", "data": values}],
            )
            charts[f"composition-chart-{composition['id']}"] = chart.as_dict()
        return charts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = SampleModelSerializer(
            self.object, context={"request": self.request}
        ).data
        component_measurements = (
            self.object.component_measurements.select_related(
                "group",
                "component",
                "basis_component",
                "analytical_method",
                "unit",
            )
            .prefetch_related("sources")
            .order_by("group__name", "component__name", "id")
        )

        persisted_compositions = self.object.compositions.all()
        if persisted_compositions.exists():
            compositions = CompositionModelSerializer(
                persisted_compositions, many=True
            ).data
            for composition in compositions:
                composition["is_derived"] = False
            charts = self._build_persisted_composition_charts(persisted_compositions)
        else:
            compositions = self._build_derived_compositions(component_measurements)
            charts = self._build_derived_composition_charts(compositions)

        data["compositions"] = compositions

        context.update(
            {
                "data": data,
                "charts": charts,
                "component_measurements": component_measurements,
            }
        )
        return context


class SampleUpdateView(UserCreatedObjectUpdateView):
    model = Sample
    form_class = SampleModelForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class SampleModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Sample


# ----------- Sample Utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Sample


class PublishedSampleAutoCompleteView(SampleAutocompleteView):
    def get_queryset(self):
        return super().get_queryset().filter(publication_status="published")


class UserOwnedSampleAutoCompleteView(SampleAutocompleteView):
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class SampleAddCompositionView(UserCreatedObjectCreateView):
    sample = None
    form_class = SampleAddCompositionForm

    def get_initial(self):
        self.sample = self.get_sample()
        return {"sample": self.sample}

    def form_valid(self, form):
        form.instance.owner = self.request.user
        composition = form.save()
        self.sample.compositions.add(composition)
        return HttpResponseRedirect(self.get_success_url())

    def get_sample(self):
        if not self.sample:
            self.sample = Sample.objects.get(pk=self.kwargs.get("pk"))
            return self.sample
        return None

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.kwargs.get("pk")})

    def get(self, request, *args, **kwargs):
        self.sample = self.get_sample()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.sample = self.get_sample()
        return super().post(request, *args, **kwargs)


class SampleAddPropertyView(UserCreatedObjectCreateView):
    form_class = MaterialPropertyValueModelForm
    permission_required = "materials.add_materialpropertyvalue"

    def form_valid(self, form):
        property_value = form.save()
        sample = Sample.objects.get(pk=self.kwargs.get("pk"))
        sample.properties.add(property_value)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.kwargs.get("pk")})


class SampleModalAddPropertyView(UserPassesTestMixin, UserCreatedObjectModalCreateView):
    form_class = MaterialPropertyValueModalModelForm
    permission_required = "materials.add_materialpropertyvalue"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        property_value = form.save()
        sample = Sample.objects.get(pk=self.kwargs.get("pk"))
        sample.properties.add(property_value)
        return HttpResponseRedirect(self.get_success_url())

    def test_func(self):
        try:
            sample = Sample.objects.get(pk=self.kwargs.get("pk"))
        except Sample.DoesNotExist:
            return False
        policy = get_object_policy(self.request.user, sample, request=self.request)
        return policy["can_add_property"]

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.kwargs.get("pk")})


class SampleCreateDuplicateView(UserCreatedObjectUpdateView):
    model = Sample
    form_class = SampleModelForm
    object = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial["name"] = f"{self.object.name} (copy)"
        return initial

    def form_valid(self, form):
        self.object = self.object.duplicate(
            creator=self.request.user, **form.cleaned_data
        )
        self.new_object = self.object
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.new_object.get_absolute_url()


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

# Not List view because compositions only make sense in the context of their materials


class CompositionCreateView(UserCreatedObjectCreateView):
    form_class = CompositionModelForm
    permission_required = "materials.add_composition"


class CompositionModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CompositionModalModelForm
    permission_required = "materials.add_composition"


class CompositionDetailView(UserCreatedObjectDetailView):
    model = Composition

    def get(self, request, *args, **kwargs):
        # Redirect to the detail page of the sample that the composition belongs to
        composition = get_object_or_404(Composition, id=kwargs.get("pk"))
        return HttpResponseRedirect(composition.sample.get_absolute_url())


class CompositionModalDetailView(UserCreatedObjectModalDetailView):
    model = Composition


class CompositionUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Composition
    form_class = CompositionModelForm
    inlines = [
        InlineWeightShare,
    ]

    def get_context_data(self, **kwargs):
        inline_helper = WeightShareUpdateFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {"inline_helper": inline_helper, "form_helper": form_helper}
        context.update(kwargs)
        return super().get_context_data(**context)


# TODO: Improve or EOL
class CompositionModalUpdateView(
    PermissionRequiredMixin, NextOrSuccessUrlMixin, UpdateWithInlinesView
):
    model = Composition
    inlines = [
        ModalInlineComponentShare,
    ]
    fields = []
    template_name = "modal_form_with_formset.html"
    permission_required = (
        "materials.change_composition",
        "materials.change_weightshare",
    )

    def get_context_data(self, **kwargs):
        inline_helper = ComponentShareDistributionFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {
            "form_title": "Change the composition",
            "submit_button_text": "Save",
            "inline_helper": inline_helper,
            "form_helper": form_helper,
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class CompositionModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Composition

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.object.sample.pk})


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddComponentView(
    PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView
):
    model = Composition
    form_class = AddComponentModalForm
    template_name = "modal_form.html"
    permission_required = "materials.add_weightshare"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {"form_title": "Select a component to add", "submit_button_text": "Add"}
        )
        return context

    def form_valid(self, form):
        self.get_object().add_component(form.cleaned_data["component"])
        return HttpResponseRedirect(self.get_success_url())


class CompositionOrderUpView(UserOwnsObjectMixin, SingleObjectMixin, RedirectView):
    model = Composition
    object = None
    permission_required = "materials.change_composition"

    def get_redirect_url(self, *args, **kwargs):
        return reverse("sample-detail", kwargs={"pk": self.object.sample.pk})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.order_up()
        return super().get(request, *args, **kwargs)


class CompositionOrderDownView(UserOwnsObjectMixin, SingleObjectMixin, RedirectView):
    model = Composition
    object = None
    permission_required = "materials.change_composition"

    def get_redirect_url(self, *args, **kwargs):
        return reverse("sample-detail", kwargs={"pk": self.object.sample.pk})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.order_down()
        return super().get(request, *args, **kwargs)


# ----------- Weight Share CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WeightShareModalDeleteView(UserCreatedObjectModalDeleteView):
    model = WeightShare

    def get_success_url(self):
        return reverse(
            "sample-detail", kwargs={"pk": self.object.composition.sample.pk}
        )


# ----------- Materials/Components/Groups Relation -----------------------------------------------------------------


class AddCompositionView(
    PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView
):
    model = SampleSeries
    form_class = AddCompositionModalForm
    template_name = "modal_form.html"
    permission_required = ("materials.add_composition", "materials.add_weightshare")
    success_message = "Composition successfully added."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": "Select a component group to add",
                "submit_button_text": "Add",
            }
        )
        return context

    def form_valid(self, form):
        self.get_object().add_component_group(
            form.cleaned_data["group"], fractions_of=form.cleaned_data["fractions_of"]
        )
        return HttpResponseRedirect(self.get_success_url())


# For removal of component groups use CompositionModalDeleteView


class AddSourceView(
    LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView
):
    form_class = AddLiteratureSourceForm
    template_name = "modal_form.html"

    def get_object(self):
        return Composition.objects.get(id=self.kwargs.get("pk"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {"form_title": "Select a source to add", "submit_button_text": "Add"}
        )
        return context

    def form_valid(self, form):
        self.get_object().sources.add(form.cleaned_data["source"])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class AddSeasonalVariationView(
    LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView
):
    form_class = AddSeasonalVariationForm
    template_name = "modal_form.html"

    def get_object(self):
        return Composition.objects.get(id=self.kwargs.get("pk"))

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields[
            "temporal_distribution"
        ].queryset = TemporalDistribution.objects.exclude(
            id__in=self.get_object().blocked_distribution_ids
        )
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {"form_title": "Select a distribution to add", "submit_button_text": "Add"}
        )
        return context

    def form_valid(self, form):
        self.get_object().add_temporal_distribution(
            form.cleaned_data["temporal_distribution"]
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class RemoveSeasonalVariationView(UserCreatedObjectDetailView):
    template_name = "modal_delete.html"
    model = Composition

    def get_distribution(self):
        return TemporalDistribution.objects.get(id=self.kwargs.get("distribution_pk"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {"form_title": "Remove seasonal variation", "submit_button_text": "Remove"}
        )
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)


class FeaturedMaterialListView(ListView):
    template_name = "featured_materials_list.html"
    model = SampleSeries

    def get_queryset(self):
        return SampleSeries.objects.filter(publish=True)


# ----------- Sample Export Views --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleExportView(SingleObjectFileExportView):
    """Export sample measurements to Excel."""

    model = Sample

    def get_task_function(self):
        """Return the Celery task, imported inline to avoid circular imports."""
        from .tasks import export_sample_measurements_to_excel

        return export_sample_measurements_to_excel
