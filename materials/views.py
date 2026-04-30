import json
import logging
from collections import defaultdict

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.db.models import Q
from django.http import (
    Http404,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.views.generic import RedirectView, TemplateView, View
from django.views.generic.detail import SingleObjectMixin

from distributions.models import TemporalDistribution
from distributions.plots import DoughnutChart
from utils.file_export.views import SingleObjectFileExportView
from utils.modal import BSModalFormView, BSModalUpdateView
from utils.object_management.models import ReviewAction
from utils.object_management.permissions import (
    filter_queryset_for_user,
    get_object_policy,
)
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    ReviewObjectFilterView,
    ReviewObjectListView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectReadAccessMixin,
    UserCreatedObjectUpdateView,
    UserOwnsObjectMixin,
)
from utils.views import NextOrSuccessUrlMixin

from .composition_normalization import (
    get_sample_composition_settings_by_group,
    get_sample_normalized_compositions,
    get_sorted_component_measurements,
)
from .filters import (
    AnalyticalMethodListFilter,
    MaterialCategoryListFilter,
    MaterialComponentGroupListFilter,
    MaterialComponentListFilter,
    MaterialListFilter,
    MaterialPropertyListFilter,
    PublishedSampleFilter,
    SampleFilter,
    SampleSeriesFilter,
    UserOwnedSampleFilter,
)
from .forms import (
    AddCompositionModalForm,
    AddLiteratureSourceForm,
    AddSeasonalVariationForm,
    AnalyticalMethodModelForm,
    ComponentGroupModalModelForm,
    ComponentGroupModelForm,
    ComponentMeasurementModalModelForm,
    ComponentMeasurementModelForm,
    ComponentModalModelForm,
    ComponentModelForm,
    Composition,
    CompositionModalModelForm,
    CompositionModelForm,
    MaterialCategoryModalModelForm,
    MaterialCategoryModelForm,
    MaterialModalModelForm,
    MaterialModelForm,
    MaterialPropertyModalModelForm,
    MaterialPropertyModelForm,
    MaterialPropertyValueModalModelForm,
    MaterialPropertyValueModelForm,
    SampleAddCompositionForm,
    SampleModalModelForm,
    SampleModelForm,
    SampleSeriesAddTemporalDistributionModalModelForm,
    SampleSeriesModalModelForm,
    SampleSeriesModelForm,
)
from .models import (
    AnalyticalMethod,
    ComponentMeasurement,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
    get_or_create_sample_substrate_category,
)
from .serializers import (
    SampleModelSerializer,
    SampleSeriesModelSerializer,
)

logger = logging.getLogger(__name__)


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


class MaterialReviewListView(ReviewObjectFilterView):
    model = Material
    queryset = Material.objects.filter(type="material")
    filterset_class = MaterialListFilter
    template_name = "materials/material_list.html"
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


class SampleSubstrateMaterialQuickCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, View
):
    """Create a substrate material directly from the sample form autocomplete."""

    permission_required = "materials.add_material"

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        name = " ".join(str(payload.get("name", "")).split())
        if not name:
            return JsonResponse(
                {"error": "A non-empty substrate name is required."},
                status=400,
            )

        substrate_category, _ = get_or_create_sample_substrate_category()
        published_material = Material.objects.filter(
            name__iexact=name,
            type="material",
            publication_status=Material.STATUS_PUBLISHED,
        ).first()
        if published_material is not None:
            return JsonResponse(
                {
                    "error": (
                        "A published material with this name already exists. "
                        "Use the existing published record."
                    ),
                    "id": published_material.pk,
                    "name": published_material.name,
                },
                status=400,
            )

        material = Material.objects.filter(
            owner=request.user,
            name__iexact=name,
            type="material",
        ).first()
        created = False
        if material is None:
            material = Material.objects.create(owner=request.user, name=name)
            created = True

        material.categories.add(substrate_category)

        return JsonResponse(
            {
                "id": material.pk,
                "name": material.name,
                "label": material.name,
                "text": material.name,
            },
            status=201 if created else 200,
        )


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


class SampleBoundCreateMixin(UserPassesTestMixin):
    sample = None
    sample_query_param = "sample"

    def dispatch(self, request, *args, **kwargs):
        self.sample = self.get_sample()
        return super().dispatch(request, *args, **kwargs)

    def get_sample(self):
        if self.sample is not None:
            return self.sample

        sample_pk = self.request.GET.get(
            self.sample_query_param
        ) or self.request.POST.get(self.sample_query_param)
        if not sample_pk:
            raise Http404("Sample query parameter is required.")

        self.sample = get_object_or_404(Sample, pk=sample_pk)
        return self.sample

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_sample"] = self.sample
        return context

    def get_success_url(self):
        return self.sample.get_absolute_url()


class MaterialPropertyValueCreateView(
    SampleBoundCreateMixin, UserCreatedObjectCreateView
):
    model = MaterialPropertyValue
    form_class = MaterialPropertyValueModelForm
    permission_required = "materials.add_materialpropertyvalue"

    def test_func(self):
        policy = get_object_policy(self.request.user, self.sample, request=self.request)
        return policy["can_add_property"]

    def form_valid(self, form):
        form.instance.sample = self.sample
        return super().form_valid(form)


class MaterialPropertyValueDetailView(
    UserCreatedObjectReadAccessMixin, SingleObjectMixin, RedirectView
):
    model = MaterialPropertyValue
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        return self.get_object().get_absolute_url()


class MaterialPropertyValueModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MaterialPropertyValue

    def get_success_url(self):
        related_sample = self.object.related_sample
        if related_sample is None:
            return ""
        return reverse("sample-detail", kwargs={"pk": related_sample.pk})


class MaterialPropertyValueUpdateView(UserCreatedObjectUpdateView):
    model = MaterialPropertyValue
    form_class = MaterialPropertyValueModelForm

    def get_success_url(self):
        return self.object.get_absolute_url()


class ComponentMeasurementCreateView(
    SampleBoundCreateMixin, UserCreatedObjectCreateView
):
    model = ComponentMeasurement
    form_class = ComponentMeasurementModelForm
    permission_required = "materials.add_componentmeasurement"

    def test_func(self):
        policy = get_object_policy(self.request.user, self.sample, request=self.request)
        return (
            self.request.user.has_perm("materials.add_componentmeasurement")
            and policy["can_manage_samples"]
        )

    def form_valid(self, form):
        form.instance.sample = self.sample
        return super().form_valid(form)


class ComponentMeasurementDetailView(
    UserCreatedObjectReadAccessMixin, SingleObjectMixin, RedirectView
):
    model = ComponentMeasurement
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        return self.get_object().get_absolute_url()


class ComponentMeasurementUpdateView(UserCreatedObjectUpdateView):
    model = ComponentMeasurement
    form_class = ComponentMeasurementModelForm

    def get_success_url(self):
        return self.object.get_absolute_url()


class ComponentMeasurementModalUpdateView(UserCreatedObjectModalUpdateView):
    model = ComponentMeasurement
    form_class = ComponentMeasurementModalModelForm

    def get_success_url(self):
        return self.object.get_absolute_url()


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        related_samples = (
            Sample.objects.filter(
                Q(property_values__analytical_method=self.object)
                | Q(component_measurements__analytical_method=self.object)
            )
            .select_related("material", "series")
            .distinct()
            .order_by("name", "pk")
        )
        context["related_samples"] = filter_queryset_for_user(
            related_samples, self.request.user
        )
        return context


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


class SampleRepresentationMixin:
    model = Sample
    filterset_class = SampleFilter
    dashboard_url = reverse_lazy("materials-explorer")

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("material", "series", "timestep")
            .prefetch_related("sources", "property_values")
        )

    def get_gallery_context_urls(self):
        try:
            public_gallery_url = reverse("sample-gallery")
        except NoReverseMatch:
            public_gallery_url = None

        try:
            private_gallery_url = reverse("sample-gallery-owned")
        except NoReverseMatch:
            private_gallery_url = None

        try:
            review_gallery_url = reverse("sample-gallery-review")
        except NoReverseMatch:
            review_gallery_url = None

        return {
            "public_gallery_url": public_gallery_url,
            "private_gallery_url": private_gallery_url,
            "review_gallery_url": review_gallery_url,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gallery_urls = self.get_gallery_context_urls()
        context.update(gallery_urls)
        if getattr(self, "representation_mode", "list") == "gallery":
            context.update(
                {
                    "representation_mode": "gallery",
                    "public_representation_url": gallery_urls["public_gallery_url"]
                    or context.get("public_url"),
                    "private_representation_url": gallery_urls["private_gallery_url"]
                    or context.get("private_url"),
                    "review_representation_url": gallery_urls["review_gallery_url"]
                    or context.get("review_url"),
                }
            )
        return context


class SamplePublishedGalleryView(SampleRepresentationMixin, PublishedObjectFilterView):
    template_name = "materials/sample_gallery.html"
    filterset_class = PublishedSampleFilter
    representation_mode = "gallery"


class SamplePrivateGalleryView(SampleRepresentationMixin, PrivateObjectFilterView):
    template_name = "materials/sample_gallery.html"
    filterset_class = UserOwnedSampleFilter
    representation_mode = "gallery"


class SampleReviewGalleryView(SampleRepresentationMixin, ReviewObjectFilterView):
    template_name = "materials/sample_gallery.html"
    representation_mode = "gallery"


class SamplePublishedListView(SampleRepresentationMixin, PublishedObjectFilterView):
    model = Sample
    filterset_class = PublishedSampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SamplePrivateListView(SampleRepresentationMixin, PrivateObjectFilterView):
    model = Sample
    filterset_class = UserOwnedSampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


class SampleReviewListView(SampleRepresentationMixin, ReviewObjectFilterView):
    model = Sample
    filterset_class = SampleFilter
    dashboard_url = reverse_lazy("materials-explorer")


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

    V2_FLAG_VALUES = {"v2", "new", "experimental"}

    def _is_v2_experience(self):
        return self.request.GET.get("experience", "").lower() in self.V2_FLAG_VALUES

    def get_template_names(self):
        if self._is_v2_experience():
            return ["materials/sample_detail_v2.html"]
        return super().get_template_names()

    @staticmethod
    def _build_completeness_checks(
        obj,
        sample_summary,
        property_values,
        component_measurements,
    ):
        has_any_measurement_data = bool(
            sample_summary["component_measurement_count"]
            or sample_summary["property_value_count"]
        )
        methods_complete = (
            has_any_measurement_data
            and all(
                measurement.analytical_method_id
                for measurement in component_measurements
            )
            and all(
                property_value.analytical_method_id
                for property_value in property_values
            )
        )
        units_complete = (
            has_any_measurement_data
            and all(measurement.unit_id for measurement in component_measurements)
            and all(property_value.unit_id for property_value in property_values)
        )

        checks = [
            {
                "label": "Description present",
                "complete": bool(obj.description),
            },
            {
                "label": "At least one source linked",
                "complete": bool(sample_summary["sample_source_count"]),
            },
            {
                "label": "At least one raw data group",
                "complete": bool(sample_summary["component_measurement_group_count"]),
            },
            {
                "label": "Normalization available",
                "complete": bool(sample_summary["composition_count"]),
            },
            {
                "label": "Units complete",
                "complete": units_complete,
            },
            {
                "label": "Methods complete",
                "complete": methods_complete,
            },
        ]
        completed_count = sum(1 for check in checks if check["complete"])
        return {
            "checks": checks,
            "completed_count": completed_count,
            "total_count": len(checks),
            "score": round((completed_count / len(checks)) * 100) if checks else 0,
            "warning_count": len(checks) - completed_count,
        }

    def _build_workflow_summary(self, completeness):
        review_actions = ReviewAction.for_object(self.object)
        review_comment_count = review_actions.filter(
            action=ReviewAction.ACTION_COMMENT
        ).count()
        return {
            "status": self.object.get_publication_status_display(),
            "owner": getattr(self.object.owner, "username", self.object.owner),
            "last_modified": self.object.lastmodified_at,
            "review_comment_count": review_comment_count,
            "validation_warning_count": completeness["warning_count"],
        }

    def _build_composition_charts(self, compositions):
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
        property_values = (
            self.object.get_property_values_queryset()
            .select_related(
                "property",
                "property__comparable_property",
                "basis_component",
                "analytical_method",
                "unit",
            )
            .prefetch_related("sources")
            .order_by("property__name", "id")
        )
        component_measurements = (
            self.object.component_measurements.select_related(
                "group",
                "component",
                "component__comparable_component",
                "basis_component",
                "analytical_method",
                "unit",
            )
            .prefetch_related("sources")
            .order_by("group__name", "component__name", "id")
        )
        composition_settings_by_group = get_sample_composition_settings_by_group(
            self.object
        )
        component_measurements = get_sorted_component_measurements(
            self.object,
            composition_settings_by_group=composition_settings_by_group,
            component_measurements=component_measurements,
        )
        compositions = get_sample_normalized_compositions(
            self.object,
            component_measurements=component_measurements,
            composition_settings_by_group=composition_settings_by_group,
        )
        charts = self._build_composition_charts(compositions)
        composition_origins = {composition["origin"] for composition in compositions}
        if len(composition_origins) > 1:
            composition_mode = "mixed"
        elif composition_origins == {"raw_derived"}:
            composition_mode = "derived"
        else:
            composition_mode = "saved"

        sample_summary = {
            "component_measurement_count": len(component_measurements),
            "component_measurement_group_count": len(
                {measurement.group_id for measurement in component_measurements}
            ),
            "property_value_count": property_values.count(),
            "composition_count": len(compositions),
            "sample_source_count": self.object.sources.count(),
        }

        sample_completeness = self._build_completeness_checks(
            self.object,
            sample_summary,
            property_values,
            component_measurements,
        )
        sample_workflow = self._build_workflow_summary(sample_completeness)
        sample_policy = get_object_policy(
            self.request.user, self.object, request=self.request
        )
        sample_layout_mode = (
            "workspace"
            if any(
                (
                    sample_policy["can_manage_samples"],
                    sample_policy["can_add_property"],
                    sample_policy["can_edit"],
                    sample_policy["can_duplicate"],
                    sample_policy["can_delete"],
                    sample_policy["can_submit_review"],
                    sample_policy["can_view_review_feedback"],
                )
            )
            else "explore"
        )

        data["compositions"] = compositions

        context.update(
            {
                "data": data,
                "charts": charts,
                "composition_mode": composition_mode,
                "property_values": property_values,
                "component_measurements": component_measurements,
                "sample_summary": sample_summary,
                "sample_completeness": sample_completeness,
                "sample_workflow": sample_workflow,
                "sample_layout_mode": sample_layout_mode,
            }
        )

        if self._is_v2_experience():
            context.update(
                self._build_v2_context(
                    compositions=compositions,
                    component_measurements=component_measurements,
                    property_values=property_values,
                    sample_policy=sample_policy,
                )
            )

        return context

    def _build_v2_context(
        self,
        compositions,
        component_measurements,
        property_values,
        sample_policy,
    ):
        """Extra context exclusively for the v2 prototype layout."""
        group_sparklines = self._build_group_sparklines(
            compositions, component_measurements
        )
        grouped_measurements = self._group_measurements_by_group_id(
            component_measurements
        )
        primary_source = self.object.sources.first()
        review_timeline = self._build_review_timeline()
        related = self._build_related_samples(limit=8)

        edit_requested = self.request.GET.get("mode", "").lower() == "edit"
        edit_mode_enabled = edit_requested and any(
            sample_policy[key]
            for key in (
                "can_manage_samples",
                "can_edit",
                "can_add_property",
            )
        )
        return {
            "group_sparklines": group_sparklines,
            "grouped_measurements": grouped_measurements,
            "primary_source": primary_source,
            "sample_policy": sample_policy,
            "review_timeline": review_timeline,
            "related_samples": related,
            "edit_mode_enabled": edit_mode_enabled,
            "edit_mode_requested": edit_requested,
        }

    @staticmethod
    def _group_measurements_by_group_id(component_measurements):
        grouped = defaultdict(list)
        for measurement in component_measurements:
            grouped[measurement.group_id].append(measurement)
        return dict(grouped)

    @staticmethod
    def _build_group_sparklines(compositions, component_measurements):
        """Tiny per-group bars for the hero composition band.

        Alongside the stacked bar we expose the dominant component so the
        sparkline carries a readable signal even at hero sizes where
        segment shading alone is too subtle.
        """
        by_group = {}
        for composition in compositions:
            group_id = composition.get("group")
            segments = [
                {
                    "label": share["component_name"],
                    "value": float(share.get("average", 0) or 0),
                }
                for share in composition.get("shares", [])
            ]
            dominant = max(segments, key=lambda seg: seg["value"]) if segments else None
            total_value = sum(seg["value"] for seg in segments)
            by_group[group_id] = {
                "group_id": group_id,
                "name": composition.get("group_name", ""),
                "anchor": f"group-{group_id}",
                "segments": segments,
                "is_derived": composition.get("is_derived", False),
                "measurement_count": 0,
                "component_count": len(segments),
                "dominant_label": dominant["label"] if dominant else "",
                "dominant_share": (
                    (dominant["value"] / total_value * 100.0)
                    if dominant and total_value
                    else 0.0
                ),
            }
        for measurement in component_measurements:
            entry = by_group.setdefault(
                measurement.group_id,
                {
                    "group_id": measurement.group_id,
                    "name": measurement.group.name,
                    "anchor": f"group-{measurement.group_id}",
                    "segments": [],
                    "is_derived": True,
                    "measurement_count": 0,
                    "component_count": 0,
                    "dominant_label": "",
                    "dominant_share": 0.0,
                },
            )
            entry["measurement_count"] += 1
        return sorted(by_group.values(), key=lambda entry: entry["name"].lower())

    def _build_review_timeline(self):
        try:
            actions = (
                ReviewAction.for_object(self.object)
                .select_related("user")
                .order_by("created_at", "id")
            )
        except Exception:
            return []
        timeline = []
        for action in actions:
            timeline.append(
                {
                    "action": action.action,
                    "label": action.get_action_display()
                    if hasattr(action, "get_action_display")
                    else action.action,
                    "user": getattr(action.user, "username", None),
                    "created_at": action.created_at,
                    "comment": getattr(action, "comment", "") or "",
                }
            )
        return timeline

    def _build_related_samples(self, limit=8):
        related = {"series": [], "material": []}
        base_qs = filter_queryset_for_user(Sample.objects.all(), self.request.user)
        if getattr(self.object, "series_id", None):
            series_qs = (
                base_qs.filter(series_id=self.object.series_id)
                .exclude(pk=self.object.pk)
                .select_related("material", "timestep")
                .order_by("timestep__order", "name")[:limit]
            )
            related["series"] = list(series_qs)
        if getattr(self.object, "material_id", None):
            exclude_pks = {self.object.pk, *(s.pk for s in related["series"])}
            material_qs = (
                base_qs.filter(material_id=self.object.material_id)
                .exclude(pk__in=exclude_pks)
                .select_related("series", "timestep")
                .order_by("-lastmodified_at")[:limit]
            )
            related["material"] = list(material_qs)
        return related


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
        sample = Sample.objects.get(pk=self.kwargs.get("pk"))
        form.instance.sample = sample
        form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.kwargs.get("pk")})


class SampleModalAddPropertyView(UserPassesTestMixin, UserCreatedObjectModalCreateView):
    form_class = MaterialPropertyValueModalModelForm
    permission_required = "materials.add_materialpropertyvalue"

    def form_valid(self, form):
        sample = Sample.objects.get(pk=self.kwargs.get("pk"))
        form.instance.owner = self.request.user
        form.instance.sample = sample
        form.save()
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


class CompositionUpdateView(UserCreatedObjectUpdateView):
    model = Composition
    form_class = CompositionModelForm

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.object.sample.pk})


class CompositionModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Composition

    def get_success_url(self):
        return reverse("sample-detail", kwargs={"pk": self.object.sample.pk})


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


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


def ensure_derived_composition_settings(sample, owner):
    composition_settings_by_group = {}
    for composition in sample.compositions.order_by("order", "id"):
        composition_settings_by_group.setdefault(composition.group_id, composition)

    default_component = MaterialComponent.objects.default()
    for measurement in sample.component_measurements.select_related("group").order_by(
        "group__name", "group_id", "id"
    ):
        if measurement.group_id in composition_settings_by_group:
            continue
        composition_settings_by_group[measurement.group_id] = (
            Composition.objects.create(
                owner=owner,
                sample=sample,
                group=measurement.group,
                fractions_of=default_component,
            )
        )

    return composition_settings_by_group


class _DerivedCompositionOrderView(
    LoginRequiredMixin, UserPassesTestMixin, RedirectView
):
    sample = None
    group = None

    def get_sample(self):
        if self.sample is None:
            self.sample = get_object_or_404(Sample, pk=self.kwargs["sample_pk"])
        return self.sample

    def get_group(self):
        if self.group is None:
            self.group = get_object_or_404(
                MaterialComponentGroup, pk=self.kwargs["group_pk"]
            )
        return self.group

    def test_func(self):
        sample = self.get_sample()
        policy = get_object_policy(self.request.user, sample, request=self.request)
        return policy["can_manage_samples"]

    def get_redirect_url(self, *args, **kwargs):
        return reverse("sample-detail", kwargs={"pk": self.get_sample().pk})


class DerivedCompositionOrderUpView(_DerivedCompositionOrderView):
    def get(self, request, *args, **kwargs):
        sample = self.get_sample()
        group = self.get_group()
        composition_settings_by_group = ensure_derived_composition_settings(
            sample, request.user
        )
        composition_settings_by_group[group.pk].order_up()
        return super().get(request, *args, **kwargs)


class DerivedCompositionOrderDownView(_DerivedCompositionOrderView):
    def get(self, request, *args, **kwargs):
        sample = self.get_sample()
        group = self.get_group()
        composition_settings_by_group = ensure_derived_composition_settings(
            sample, request.user
        )
        composition_settings_by_group[group.pk].order_down()
        return super().get(request, *args, **kwargs)


# ----------- Materials/Components/Groups Relation -----------------------------------------------------------------


class AddCompositionView(
    PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView
):
    model = SampleSeries
    form_class = AddCompositionModalForm
    template_name = "modal_form.html"
    permission_required = "materials.add_composition"
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
            {
                "form_title": "Select a reference to add",
                "submit_button_text": "Add",
            }
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
            {
                "form_title": "Select a distribution to add",
                "submit_button_text": "Add",
            }
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
            {
                "form_title": "Remove seasonal variation",
                "submit_button_text": "Remove",
            }
        )
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)


# ----------- Sample Export Views --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleExportView(SingleObjectFileExportView):
    """Export sample measurements to Excel."""

    model = Sample

    def get_task_function(self):
        """Return the Celery task, imported inline to avoid circular imports."""
        from .tasks import export_sample_measurements_to_excel

        return export_sample_measurements_to_excel
