import hashlib
import json
from datetime import date, timedelta
from urllib.parse import urlencode

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Min, Prefetch, Q
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from bibliography.views import (
    SourceCheckUrlView,
    SourceCreateView,
    SourceModalCreateView,
    SourceModalDeleteView,
    SourceModalDetailView,
)
from maps.filters import CatchmentFilterSet
from maps.forms import NutsAndLauCatchmentQueryForm
from maps.views import (
    CatchmentCreateView,
    CatchmentDetailView,
    CatchmentUpdateView,
    GeoDataSetFormMixin,
    GeoDataSetPrivateFilteredMapView,
    GeoDataSetPublishedFilteredMapView,
    GeoDataSetReviewFilteredMapView,
    MapMixin,
)
from utils.file_export.views import GenericUserCreatedObjectExportView
from utils.forms import M2MInlineFormSetMixin
from utils.object_management.permissions import (
    filter_queryset_for_user,
    get_object_policy,
)
from utils.object_management.views import (
    ApproveItemModalView,
    ApproveItemView,
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    RejectItemModalView,
    RejectItemView,
    ReviewItemDetailView,
    ReviewObjectFilterView,
    SubmitForReviewModalView,
    SubmitForReviewView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalArchiveView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    WithdrawFromReviewModalView,
    WithdrawFromReviewView,
)

from .filters import (
    CollectionFilterSet,
    CollectionFrequencyListFilter,
    CollectionSystemListFilter,
    CollectorFilter,
    FeeSystemListFilter,
    WasteCategoryListFilter,
    WasteComponentListFilter,
    WasteFlyerFilter,
)
from .forms import (
    AggregatedCollectionPropertyValueModelForm,
    CollectionAddPredecessorForm,
    CollectionAddWasteSampleForm,
    CollectionFrequencyModalModelForm,
    CollectionFrequencyModelForm,
    CollectionModelForm,
    CollectionPropertyValueModelForm,
    CollectionRemovePredecessorForm,
    CollectionRemoveWasteSampleForm,
    CollectionSeasonForm,
    CollectionSeasonFormHelper,
    CollectionSeasonFormSet,
    CollectionSystemModalModelForm,
    CollectionSystemModelForm,
    CollectorModalModelForm,
    CollectorModelForm,
    FeeSystemModelForm,
    WasteCategoryModalModelForm,
    WasteCategoryModelForm,
    WasteComponentModalModelForm,
    WasteComponentModelForm,
    WasteFlyerFormSet,
    WasteFlyerFormSetHelper,
    WasteFlyerModalModelForm,
    WasteFlyerModelForm,
)
from .models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
)
from .tasks import check_wasteflyer_urls


class CollectionExplorerView(TemplateView):
    template_name = "wastecollection_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collection_count"] = Collection.objects.filter(
            publication_status="published"
        ).count()
        context["catchment_count"] = CollectionCatchment.objects.filter(
            publication_status="published"
        ).count()
        context["collector_count"] = Collector.objects.filter(
            publication_status="published"
        ).count()
        context["wastecategory_count"] = WasteCategory.objects.filter(
            publication_status="published"
        ).count()
        context["collectionsystem_count"] = CollectionSystem.objects.filter(
            publication_status="published"
        ).count()
        context["feesystem_count"] = FeeSystem.objects.filter(
            publication_status="published"
        ).count()
        context["frequency_count"] = CollectionFrequency.objects.filter(
            publication_status="published"
        ).count()
        context["wastecomponent_count"] = WasteComponent.objects.filter(
            publication_status="published"
        ).count()
        context["wasteflyer_count"] = WasteFlyer.objects.filter(
            publication_status="published"
        ).count()
        return context


class CollectionDiagramView(TemplateView):
    template_name = "wastecollection_diagram.html"


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorPublishedListView(PublishedObjectFilterView):
    model = Collector
    filterset_class = CollectorFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectorPrivateListView(PrivateObjectFilterView):
    model = Collector
    filterset_class = CollectorFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectorCreateView(UserCreatedObjectCreateView):
    form_class = CollectorModelForm
    permission_required = "soilcom.add_collector"


class CollectorModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CollectorModalModelForm
    permission_required = "soilcom.add_collector"


class CollectorDetailView(UserCreatedObjectDetailView):
    model = Collector


class CollectorModalDetailView(UserCreatedObjectModalDetailView):
    model = Collector


class CollectorUpdateView(UserCreatedObjectUpdateView):
    model = Collector
    form_class = CollectorModelForm


class CollectorModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Collector
    form_class = CollectorModalModelForm


class CollectorModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Collector


# ----------- Collector Utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Collector


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionSystemPublishedListView(PublishedObjectFilterView):
    model = CollectionSystem
    filterset_class = CollectionSystemListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionSystemPrivateListView(PrivateObjectFilterView):
    model = CollectionSystem
    filterset_class = CollectionSystemListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionSystemAutocompleteView(UserCreatedObjectAutocompleteView):
    model = CollectionSystem


class CollectionSystemCreateView(UserCreatedObjectCreateView):
    form_class = CollectionSystemModelForm
    permission_required = "soilcom.add_collectionsystem"


class CollectionSystemModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CollectionSystemModalModelForm
    permission_required = "soilcom.add_collectionsystem"


class CollectionSystemDetailView(UserCreatedObjectDetailView):
    model = CollectionSystem


class CollectionSystemModalDetailView(UserCreatedObjectModalDetailView):
    model = CollectionSystem


class CollectionSystemUpdateView(UserCreatedObjectUpdateView):
    model = CollectionSystem
    form_class = CollectionSystemModelForm


class CollectionSystemModalUpdateView(UserCreatedObjectModalUpdateView):
    model = CollectionSystem
    form_class = CollectionSystemModalModelForm


class CollectionSystemModalDeleteView(UserCreatedObjectModalDeleteView):
    model = CollectionSystem


# ----------- Waste Stream Category CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteCategoryPublishedListView(PublishedObjectFilterView):
    model = WasteCategory
    filterset_class = WasteCategoryListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class WasteCategoryPrivateListView(PrivateObjectFilterView):
    model = WasteCategory
    filterset_class = WasteCategoryListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class WasteCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    model = WasteCategory


class WasteCategoryCreateView(UserCreatedObjectCreateView):
    form_class = WasteCategoryModelForm
    permission_required = "soilcom.add_wastecategory"


class WasteCategoryModalCreateView(UserCreatedObjectModalCreateView):
    form_class = WasteCategoryModalModelForm
    permission_required = "soilcom.add_wastecategory"


class WasteCategoryDetailView(UserCreatedObjectDetailView):
    model = WasteCategory


class WasteCategoryModalDetailView(UserCreatedObjectModalDetailView):
    model = WasteCategory


class WasteCategoryUpdateView(UserCreatedObjectUpdateView):
    model = WasteCategory
    form_class = WasteCategoryModelForm


class WasteCategoryModalUpdateView(UserCreatedObjectModalUpdateView):
    model = WasteCategory
    form_class = WasteCategoryModalModelForm


class WasteCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    model = WasteCategory


# ----------- Waste Component CRUD -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteComponentPublishedListView(PublishedObjectFilterView):
    model = WasteComponent
    filterset_class = WasteComponentListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class WasteComponentPrivateListView(PrivateObjectFilterView):
    model = WasteComponent
    filterset_class = WasteComponentListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class WasteComponentAutocompleteView(UserCreatedObjectAutocompleteView):
    model = WasteComponent


class WasteComponentCreateView(UserCreatedObjectCreateView):
    form_class = WasteComponentModelForm
    permission_required = "soilcom.add_wastecomponent"


class WasteComponentModalCreateView(UserCreatedObjectModalCreateView):
    form_class = WasteComponentModalModelForm
    permission_required = "soilcom.add_wastecomponent"


class WasteComponentDetailView(UserCreatedObjectDetailView):
    model = WasteComponent


class WasteComponentModalDetailView(UserCreatedObjectModalDetailView):
    model = WasteComponent


class WasteComponentUpdateView(UserCreatedObjectUpdateView):
    model = WasteComponent
    form_class = WasteComponentModelForm


class WasteComponentModalUpdateView(UserCreatedObjectModalUpdateView):
    model = WasteComponent
    form_class = WasteComponentModalModelForm


class WasteComponentModalDeleteView(UserCreatedObjectModalDeleteView):
    model = WasteComponent


# ----------- Fee System CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FeeSystemPublishedListView(PublishedObjectFilterView):
    model = FeeSystem
    filterset_class = FeeSystemListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class FeeSystemPrivateListView(PrivateObjectFilterView):
    model = FeeSystem
    filterset_class = FeeSystemListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class FeeSystemAutocompleteView(UserCreatedObjectAutocompleteView):
    model = FeeSystem


class FeeSystemCreateView(UserCreatedObjectCreateView):
    form_class = FeeSystemModelForm
    permission_required = "soilcom.add_feesystem"


class FeeSystemDetailView(UserCreatedObjectDetailView):
    model = FeeSystem


class FeeSystemUpdateView(UserCreatedObjectUpdateView):
    model = FeeSystem
    form_class = FeeSystemModelForm


class FeeSystemModalDeleteView(UserCreatedObjectModalDeleteView):
    model = FeeSystem


# ----------- Waste Collection Flyer CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerPublishedFilterView(PublishedObjectFilterView):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")
    ordering = "id"


class WasteFlyerPrivateFilterView(PrivateObjectFilterView):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")
    ordering = "id"


class WasteFlyerCreateView(SourceCreateView):
    form_class = WasteFlyerModelForm
    success_url = reverse_lazy("wasteflyer-list")
    permission_required = "soilcom.add_wasteflyer"

    def form_valid(self, form):
        form.instance.type = "waste_flyer"
        return super().form_valid(form)


class WasteFlyerModalCreateView(SourceModalCreateView):
    form_class = WasteFlyerModalModelForm
    success_url = reverse_lazy("wasteflyer-list")
    permission_required = "soilcom.add_wasteflyer"

    def form_valid(self, form):
        form.instance.type = "waste_flyer"
        return super().form_valid(form)


class WasteFlyerDetailView(UserCreatedObjectDetailView):
    model = WasteFlyer


class WasteFlyerModalDetailView(SourceModalDetailView):
    template_name = "modal_waste_flyer_detail.html"
    model = WasteFlyer


# There is no WasteFlyerUpdateView because wasteflyers are not managed separately only through the collections
# they are connected to.


class WasteFlyerModalDeleteView(SourceModalDeleteView):
    success_url = reverse_lazy("wasteflyer-list")


# ----------- Waste Collection Flyer utils -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerCheckUrlView(SourceCheckUrlView):
    model = WasteFlyer
    permission_required = "soilcom.change_wasteflyer"


class WasteFlyerCheckUrlProgressView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            "state": result.state,
            "details": result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class WasteFlyerListCheckUrlsView(PermissionRequiredMixin, View):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    permission_required = "soilcom.change_wasteflyer"

    @staticmethod
    def get(request, *args, **kwargs):
        params = request.GET.copy()
        params.pop("csrfmiddlewaretoken", None)
        params.pop("page", None)
        task = check_wasteflyer_urls.delay(params)
        callback_id = task.get()[0][0]
        response_data = {"task_id": callback_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class WasteFlyerListCheckUrlsProgressView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            "state": result.state,
            "details": result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type="application/json")


# ----------- Frequency CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FrequencyPublishedListView(PublishedObjectFilterView):
    model = CollectionFrequency
    filterset_class = CollectionFrequencyListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class FrequencyPrivateListView(PrivateObjectFilterView):
    model = CollectionFrequency
    filterset_class = CollectionFrequencyListFilter
    dashboard_url = reverse_lazy("wastecollection-explorer")


class FrequencyCreateView(M2MInlineFormSetMixin, UserCreatedObjectCreateView):
    form_class = CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = CollectionSeasonFormSet
    formset_form_class = CollectionSeasonForm
    formset_helper_class = CollectionSeasonFormHelper
    formset_factory_kwargs = {"extra": 0}
    relation_field_name = "seasons"
    permission_required = "soilcom.add_collectionfrequency"
    template_name = "formsets_card.html"

    def get_formset_initial(self):
        return list(
            CollectionSeason.objects.filter(
                distribution__name="Months of the year",
                first_timestep__name="January",
                last_timestep__name="December",
            ).values("distribution", "first_timestep", "last_timestep")
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            form.instance.owner = self.request.user
            self.object = form.save()
            # Update formset's parent_object so it can set the M2M relationship
            formset.parent_object = self.object
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class FrequencyDetailView(UserCreatedObjectDetailView):
    model = CollectionFrequency


class FrequencyModalDetailView(UserCreatedObjectModalDetailView):
    model = CollectionFrequency


class FrequencyUpdateView(M2MInlineFormSetMixin, UserCreatedObjectUpdateView):
    model = CollectionFrequency
    form_class = CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = CollectionSeasonFormSet
    formset_form_class = CollectionSeasonForm
    formset_helper_class = CollectionSeasonFormHelper
    formset_factory_kwargs = {"extra": 0}
    relation_field_name = "seasons"
    template_name = "formsets_card.html"

    def get_formset_initial(self):
        initial = []
        for season in self.object.seasons.all():
            options = CollectionCountOptions.objects.get(
                frequency=self.object, season=season
            )
            initial.append(
                {
                    "distribution": season.distribution,
                    "first_timestep": season.first_timestep,
                    "last_timestep": season.last_timestep,
                    "standard": options.standard,
                    "option_1": options.option_1,
                    "option_2": options.option_2,
                    "option_3": options.option_3,
                }
            )
        return initial

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class FrequencyModalUpdateView(UserCreatedObjectModalUpdateView):
    model = CollectionFrequency
    form_class = CollectionFrequencyModalModelForm


class FrequencyModalDeleteView(UserCreatedObjectModalDeleteView):
    model = CollectionFrequency


# ----------- Frequency Utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FrequencyAutocompleteView(UserCreatedObjectAutocompleteView):
    model = CollectionFrequency


# ----------- CollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCreateView(
    M2MInlineFormSetMixin, UserCreatedObjectCreateView
):
    form_class = CollectionPropertyValueModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "sources"
    permission_required = "soilcom.add_collectionpropertyvalue"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            return self.forms_valid(form, formset)
        else:
            return self.forms_invalid(form, formset)

    def forms_valid(self, form, formset):
        form.instance.owner = self.request.user
        self.object = form.save()
        # Update formset's parent_object so it can set the M2M relationship
        formset.parent_object = self.object
        formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, form, formset):
        context = self.get_context_data(form=form, formset=formset)
        return self.render_to_response(context)


class CollectionPropertyValueDetailView(UserCreatedObjectDetailView):
    model = CollectionPropertyValue


class CollectionPropertyValueUpdateView(
    M2MInlineFormSetMixin, UserCreatedObjectUpdateView
):
    model = CollectionPropertyValue
    form_class = CollectionPropertyValueModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "sources"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            return self.forms_valid(form, formset)
        else:
            return self.forms_invalid(form, formset)

    def forms_valid(self, form, formset):
        instance = form.instance
        anchor = instance.collection.version_anchor if instance.collection else None
        if anchor and instance.collection_id != anchor.pk:
            instance.collection = anchor

        self.object = form.save()

        # Capture bibliographic sources saved by the form before the formset
        # overwrites the sources M2M via .set() with only WasteFlyer objects.
        bibliographic_sources = list(
            self.object.sources.exclude(type="waste_flyer").values_list("pk", flat=True)
        )

        # Update formset's parent_object so it can set the M2M relationship
        formset.parent_object = self.object
        formset.save()

        # Re-add bibliographic sources that were wiped by formset.save()
        if bibliographic_sources:
            self.object.sources.add(*bibliographic_sources)

        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, form, formset):
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


class CollectionPropertyValueModalDeleteView(UserCreatedObjectModalDeleteView):
    model = CollectionPropertyValue

    def form_valid(self, form):
        # Ensure we delete the anchor record for the same (property, unit, year)
        # when the user deletes a CPV on a non-anchor collection.
        self.object = self.get_object()
        anchor = self.object.collection.version_anchor
        anchor_value = None
        if anchor and self.object.collection_id != anchor.pk:
            try:
                anchor_value = CollectionPropertyValue.objects.get(
                    collection=anchor,
                    property=self.object.property,
                    unit=self.object.unit,
                    year=self.object.year,
                )
            except CollectionPropertyValue.DoesNotExist:
                anchor_value = None

        # Delete anchor first if it is distinct from the current object
        if anchor_value and anchor_value.pk != self.object.pk:
            anchor_value.delete()

        return super().form_valid(form)

    def get_success_url(self):
        anchor = self.object.collection.version_anchor
        target = anchor.pk if anchor else self.object.collection.pk
        return reverse("collection-detail", kwargs={"pk": target})


# ----------- AggregatedCollectionPropertyValue CRUD -------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCreateView(
    M2MInlineFormSetMixin, UserCreatedObjectCreateView
):
    template_name = "soilcom/collectionpropertyvalue_form.html"
    form_class = AggregatedCollectionPropertyValueModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "sources"
    permission_required = "soilcom.add_aggregatedcollectionpropertyvalue"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)


class AggregatedCollectionPropertyValueDetailView(UserCreatedObjectDetailView):
    model = AggregatedCollectionPropertyValue


class AggregatedCollectionPropertyValueUpdateView(
    M2MInlineFormSetMixin, UserCreatedObjectUpdateView
):
    template_name = "soilcom/collectionpropertyvalue_form.html"
    model = AggregatedCollectionPropertyValue
    form_class = AggregatedCollectionPropertyValueModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "sources"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)


class AggregatedCollectionPropertyValueModalDeleteView(
    UserCreatedObjectModalDeleteView
):
    model = AggregatedCollectionPropertyValue

    def get_success_url(self):
        related_ids = list(self.object.collections.values_list("id", flat=True))
        base_url = reverse("collection-list")
        query_string = urlencode([("id", rid) for rid in related_ids])
        return f"{base_url}?{query_string}"


# ----------- CollectionCatchment CRUD ---------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCatchmentPublishedFilterView(PublishedObjectFilterView):
    model = CollectionCatchment
    filterset_class = CatchmentFilterSet
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionCatchmentPrivateFilterView(PrivateObjectFilterView):
    model = CollectionCatchment
    filterset_class = CatchmentFilterSet
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionCatchmentCreateView(CatchmentCreateView):
    permission_required = "soilcom.add_collectioncatchment"


class CollectionCatchmentDetailView(CatchmentDetailView):
    model = CollectionCatchment

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        try:
            visible_collections = list(
                filter_queryset_for_user(self.object.downstream_collections, user)
            )
        except Exception:
            visible_collections = []

        status_key_map = {
            Collection.STATUS_PUBLISHED: "published",
            Collection.STATUS_REVIEW: "review",
            Collection.STATUS_PRIVATE: "private",
            Collection.STATUS_DECLINED: "declined",
            Collection.STATUS_ARCHIVED: "archived",
        }
        grouped = {key: [] for key in status_key_map.values()}

        for collection in visible_collections:
            key = status_key_map.get(collection.publication_status)
            if key:
                grouped[key].append(collection)

        context.update(
            {
                "downstream_published_collections": grouped["published"],
                "downstream_review_collections": grouped["review"],
                "downstream_private_collections": grouped["private"],
                "downstream_declined_collections": grouped["declined"],
                "downstream_archived_collections": grouped["archived"],
            }
        )
        return context


class CollectionCatchmentUpdateView(CatchmentUpdateView):
    def get_success_url(self):
        return reverse("collectioncatchment-detail", kwargs={"pk": self.object.pk})


class CollectionCatchmentModalDeleteView(UserCreatedObjectModalDeleteView):
    model = CollectionCatchment

    def get_success_url(self):
        if self.object.publication_status == "published":
            return f"{reverse('collectioncatchment-list')}?scope=published"
        elif self.object.publication_status == "private":
            return f"{reverse('collectioncatchment-list-owned')}?scope=private"


# ----------- CollectionCatchment Utils -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCatchmentAutocompleteView(UserCreatedObjectAutocompleteView):
    model = CollectionCatchment
    geodataset_model_name = "WasteCollection"


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionListMixin:
    """Mixin providing optimized queryset for Collection list views."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "catchment__region",
                "waste_stream__category",
                "collector",
                "collection_system",
            )
        )


class CollectionPublishedListView(CollectionListMixin, PublishedObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionPrivateListView(CollectionListMixin, PrivateObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionReviewListView(CollectionListMixin, ReviewObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    template_name = "collection_review_filter.html"
    dashboard_url = reverse_lazy("wastecollection-explorer")


class CollectionCreateView(M2MInlineFormSetMixin, UserCreatedObjectCreateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "flyers"
    permission_required = "soilcom.add_collection"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if "region_id" in self.request.GET:
            region_id = self.request.GET.get("region_id")
            catchment = CollectionCatchment.objects.get(id=region_id)
            initial["catchment"] = catchment
        if "collector" in self.request.GET:
            initial["collector"] = Collector.objects.get(
                id=self.request.GET.get("collector")
            )
        initial["valid_from"] = date.today()
        return initial

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            form.instance.owner = self.request.user
            self.object = form.save()
            # Update formset's parent_object so it can set the M2M relationship
            formset.parent_object = self.object
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionCopyView(CollectionCreateView):
    """
    View for duplicating an existing Collection. Copies all relevant fields and resets instance for new object creation.
    """

    model = Collection

    def get_initial(self):
        """
        Returns initial data for the duplicate form, including all relevant fields from the original collection.
        """
        initial = model_to_dict(self.object)
        initial.update(
            {
                "waste_category": self.object.waste_stream.category.id,
                "allowed_materials": [
                    mat.id for mat in self.object.waste_stream.allowed_materials.all()
                ],
                "forbidden_materials": [
                    mat.id for mat in self.object.waste_stream.forbidden_materials.all()
                ],
            }
        )
        self.object = None
        return initial

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


class CollectionCreateNewVersionView(CollectionCopyView):
    """
    View for creating a new version of a Collection. Inherits duplication logic and sets predecessor.
    """

    predecessor = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        predecessor = self.predecessor or getattr(self, "object", None)
        if predecessor is not None:
            kwargs["predecessor"] = predecessor
        return kwargs

    def get_initial(self):
        """
        Returns initial data for the new version form, including all relevant fields from the original collection.
        """
        initial = model_to_dict(self.object)
        initial.update(
            {
                "waste_category": self.object.waste_stream.category.id,
                "allowed_materials": [
                    mat.id for mat in self.object.waste_stream.allowed_materials.all()
                ],
                "forbidden_materials": [
                    mat.id for mat in self.object.waste_stream.forbidden_materials.all()
                ],
            }
        )
        if self.object.valid_until:
            initial["valid_from"] = self.object.valid_until + timedelta(days=1)
        else:
            initial["valid_from"] = None
        self.predecessor = self.object
        self.object = None
        return initial

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            form.instance.owner = self.request.user
            self.predecessor = self.get_object()
            self.object = form.save()
            self.object.add_predecessor(self.predecessor)
            formset.parent_object = self.object
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Collection
    features_layer_api_basename = "api-waste-collection"
    map_title = "Collection"

    def get_queryset(self):
        """Optimize queries by prefetching related sources and flyers."""
        return (
            super()
            .get_queryset()
            .select_related(
                "owner",
                "catchment",
                "collector",
                "collection_system",
                "waste_stream__category",
                "frequency",
                "fee_system",
            )
            .prefetch_related(
                "sources",
                "flyers",
                "predecessors",
                "successors",
                "waste_stream__allowed_materials",
                "waste_stream__forbidden_materials",
                "samples",
                "frequency__collectioncountoptions_set",
            )
        )

    def get_override_params(self):
        params = super().get_override_params()
        # Always load the features layer for the current object on detail pages
        params["load_features"] = True
        return params

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Add chain-aware property values visible to the current user
        cpvs = self.object.collectionpropertyvalues_for_display(user=user)
        agg_cpvs = self.object.aggregatedcollectionpropertyvalues_for_display(user=user)

        # On published collections, show only published property values to maintain
        # public consistency, UNLESS the viewer is the collection owner
        is_owner = (
            hasattr(self.object, "owner")
            and hasattr(user, "id")
            and self.object.owner_id == user.id
        )
        if self.object.publication_status == "published" and not is_owner:
            cpvs = [
                v for v in cpvs if getattr(v, "publication_status", None) == "published"
            ]
            agg_cpvs = [
                v
                for v in agg_cpvs
                if getattr(v, "publication_status", None) == "published"
            ]

        context["collection_property_values"] = cpvs
        context["aggregated_collection_property_values"] = agg_cpvs

        waste_stream = getattr(self.object, "waste_stream", None)
        context["allowed_materials"] = (
            list(waste_stream.allowed_materials.all()) if waste_stream else []
        )
        context["forbidden_materials"] = (
            list(waste_stream.forbidden_materials.all()) if waste_stream else []
        )
        context["samples"] = list(self.object.samples.all())

        # Collect all sources from collection, flyers, CPVs, and ACPVs
        all_sources = set()

        # Sources directly on the collection
        for source in self.object.sources.all():
            all_sources.add(source)

        # Flyers are also sources (WasteFlyer is a proxy of Source)
        for flyer in self.object.flyers.all():
            all_sources.add(flyer)

        # Sources from collection property values
        for cpv in cpvs:
            for source in cpv.sources.all():
                all_sources.add(source)

        # Sources from aggregated collection property values
        for acpv in agg_cpvs:
            for source in acpv.sources.all():
                all_sources.add(source)

        # Sort sources by abbreviation for consistent display
        context["all_sources"] = sorted(all_sources, key=lambda s: s.abbreviation)

        # Filter version chain links (predecessors/successors) by user visibility
        try:
            context["visible_successors"] = filter_queryset_for_user(
                self.object.successors.all(), user
            )
        except Exception:
            context["visible_successors"] = self.object.successors.none()

        predecessors_qs = (
            self.object.predecessors.all()
            .select_related("owner")
            .order_by("-lastmodified_at", "-pk")
        )
        try:
            context["visible_predecessors"] = filter_queryset_for_user(
                predecessors_qs, user
            )
        except Exception:
            context["visible_predecessors"] = self.object.predecessors.none()

        return context


class CollectionModalDetailView(UserCreatedObjectModalDetailView):
    model = Collection


class CollectionReviewActionCascadeMixin:
    """
    Cascade review actions from Collections to related property values.

    When a Collection's review state changes (submit, withdraw, reject, approve),
    this mixin cascades the action to CollectionPropertyValues and
    AggregatedCollectionPropertyValues across the entire version chain.
    """

    def post_action_hook(self, request, previous_status=None):
        """Delegate to the base hook (model cascade is handled centrally)."""
        super().post_action_hook(request, previous_status)


class CollectionReviewItemDetailView(ReviewItemDetailView):
    """
    Collection-specific review detail view with property value preview.

    Extends the base review view to show collection property values and
    aggregated property values with review-aware deduplication logic.
    """

    model = Collection

    def get_object(self, queryset=None):
        """Fetch the Collection with all related objects prefetched to minimize queries."""
        if hasattr(self, "object") and self.object is not None:
            return self.object

        content_type_id = self.kwargs.get("content_type_id")
        object_id = self.kwargs.get("object_id")

        qs = Collection.objects.select_related(
            "owner",
            "catchment",
            "collector",
            "collection_system",
            "waste_stream",
            "waste_stream__category",
            "frequency",
            "fee_system",
        ).prefetch_related(
            "sources",
            "flyers",
            "samples",
            "predecessors",
            "successors",
            "waste_stream__allowed_materials",
            "waste_stream__forbidden_materials",
            Prefetch(
                "frequency__collectioncountoptions_set",
                queryset=CollectionCountOptions.objects.select_related(
                    "season", "season__first_timestep", "season__last_timestep"
                ),
            ),
        )

        if content_type_id and object_id:
            obj = get_object_or_404(qs, pk=object_id)
        else:
            obj = get_object_or_404(qs, pk=self.kwargs.get("pk"))

        self.object = obj
        return obj

    def get_review_specific_context(self, context):
        """Add collection property values for review preview."""
        obj = self.object
        review_context = {}

        # For review preview, show CPVs with status in {published, review},
        # preferring review over published for the same (property, unit, year) key
        try:
            if hasattr(obj, "all_versions") and hasattr(
                obj, "_deduplicate_property_values"
            ):
                from django.db.models import Case, IntegerField, Value, When

                cpv_qs = (
                    CollectionPropertyValue.objects.filter(
                        collection__in=obj.all_versions(),
                        publication_status__in=["published", "review"],
                    )
                    .select_related("property", "unit", "collection", "owner")
                    .prefetch_related("sources")
                )

                # Order by property/unit/year, then prefer review (0) over published (1)
                cpv_qs = cpv_qs.annotate(
                    review_order=Case(
                        When(publication_status="review", then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    )
                ).order_by(
                    "property__name",
                    "unit__name",
                    "year",
                    "review_order",
                    "-collection__valid_from",
                    "-collection__pk",
                    "pk",
                )

                review_context["collection_property_values"] = (
                    obj._deduplicate_property_values(cpv_qs)
                )
        except Exception:
            pass

        # Same logic for aggregated property values
        try:
            if hasattr(obj, "all_versions"):
                from django.db.models import Case, IntegerField, Value, When

                agg_qs = (
                    AggregatedCollectionPropertyValue.objects.filter(
                        collections__in=obj.all_versions(),
                        publication_status__in=["published", "review"],
                    )
                    .select_related("property", "unit", "owner")
                    .prefetch_related("collections", "sources")
                    .distinct()
                )

                agg_qs = agg_qs.annotate(
                    review_order=Case(
                        When(publication_status="review", then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    )
                ).order_by(
                    "property__name",
                    "unit__name",
                    "year",
                    "review_order",
                    "-created_at",
                    "-pk",
                )

                # Deduplicate aggregated values by (property, unit, year)
                seen = set()
                agg_values = []
                for val in agg_qs:
                    key = (val.property_id, val.unit_id, val.year)
                    if key not in seen:
                        seen.add(key)
                        agg_values.append(val)

                review_context["aggregated_collection_property_values"] = agg_values
        except Exception:
            pass

        # Collect all sources from collection, flyers, CPVs, and ACPVs
        try:
            all_sources = set()

            # Sources directly on the collection
            for source in obj.sources.all():
                all_sources.add(source)

            # Flyers are also sources (WasteFlyer is a proxy of Source)
            for flyer in obj.flyers.all():
                all_sources.add(flyer)

            # Sources from collection property values (if available in context)
            cpvs = review_context.get("collection_property_values", [])
            for cpv in cpvs:
                for source in cpv.sources.all():
                    all_sources.add(source)

            # Sources from aggregated collection property values (if available in context)
            agg_cpvs = review_context.get("aggregated_collection_property_values", [])
            for acpv in agg_cpvs:
                for source in acpv.sources.all():
                    all_sources.add(source)

            # Sort sources by abbreviation for consistent display
            review_context["all_sources"] = sorted(
                all_sources, key=lambda s: s.abbreviation
            )
        except Exception:
            pass

        return review_context


# Register the specialized review view for Collection model
# This allows the generic object_management:review_item_detail URL to automatically
# delegate to this view when reviewing Collection objects
CollectionReviewItemDetailView.register_for_model(Collection)


class CollectionUpdateView(M2MInlineFormSetMixin, UserCreatedObjectUpdateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = WasteFlyerFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = WasteFlyerFormSetHelper
    relation_field_name = "flyers"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({"owner": self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            {
                "waste_category": self.object.waste_stream.category.id,
                "allowed_materials": [
                    mat.id for mat in self.object.waste_stream.allowed_materials.all()
                ],
                "forbidden_materials": [
                    mat.id for mat in self.object.waste_stream.forbidden_materials.all()
                ],
            }
        )
        return initial

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Collection


class CollectionReviewFilterView(ReviewObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    dashboard_url = reverse_lazy("wastecollection-explorer")

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "review"
        kwargs["data"] = data
        return kwargs


# ----------- Collection Utils -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Collection


class CollectionListFileExportView(GenericUserCreatedObjectExportView):
    model_label = "soilcom.Collection"


class CollectionAddPropertyValueView(CollectionPropertyValueCreateView):
    # TODO: Handle permissions without overriding dispatch
    def dispatch(self, request, *args, **kwargs):
        # Let parent handle authentication first
        result = super().dispatch(request, *args, **kwargs)

        # Only check policy for authenticated requests that passed parent checks
        if request.user.is_authenticated and request.method in ("GET", "POST"):
            try:
                self.parent_collection = Collection.objects.get(pk=kwargs.get("pk"))
            except Collection.DoesNotExist as err:
                raise PermissionDenied("Invalid parent collection.") from err

            policy = get_object_policy(
                request.user, self.parent_collection, request=request
            )
            if not policy.get("can_add_property"):
                raise PermissionDenied(
                    "You do not have permission to add statistics to this collection."
                )

            self.anchor_collection = (
                self.parent_collection.version_anchor or self.parent_collection
            )

        return result

    def get_initial(self):
        initial = super().get_initial()
        anchor = getattr(self, "anchor_collection", None)
        initial["collection"] = anchor.pk if anchor else self.kwargs["pk"]
        return initial

    def get_success_url(self):
        return reverse("collection-detail", kwargs={"pk": self.kwargs["pk"]})

    def forms_valid(self, form, formset):
        """
        Enforce that the new property value is attached to the anchor Collection
        referenced in the URL, regardless of any submitted form value.
        """
        anchor = getattr(self, "anchor_collection", None)
        if not anchor:
            try:
                parent = Collection.objects.get(pk=self.kwargs.get("pk"))
                anchor = parent.version_anchor or parent
            except Collection.DoesNotExist as err:
                raise PermissionDenied("Invalid parent collection.") from err
        form.instance.collection = anchor
        return super().forms_valid(form, formset)


class CollectionCatchmentAddAggregatedPropertyView(
    AggregatedCollectionPropertyValueCreateView
):
    def get_initial(self):
        initial = super().get_initial()
        catchment = CollectionCatchment.objects.get(pk=self.kwargs.get("pk"))
        initial["collections"] = catchment.downstream_collections
        return initial


class SelectNewlyCreatedObjectModelSelectOptionsView(OwnedObjectModelSelectOptionsView):
    def get_selected_object(self):
        # TODO: Improve this by adding owner to
        created_at = self.model.objects.aggregate(max_created_at=Max("created_at"))[
            "max_created_at"
        ]
        return self.model.objects.get(created_at=created_at)


class CollectorOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = Collector
    permission_required = "soilcom.view_collector"


class CollectionSystemOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = CollectionSystem
    permission_required = "soilcom.view_collectionsystem"


class CollectionFrequencyOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = CollectionFrequency
    permission_required = "soilcom.view_collectionfrequency"


class WasteCategoryOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = WasteCategory
    permission_required = "soilcom.view_wastecategory"
    template_name = "detail_with_options.html"


class CollectionWasteSamplesView(UserCreatedObjectUpdateView):
    template_name = "collection_samples.html"
    model = Collection
    form_class = CollectionAddWasteSampleForm

    def get_success_url(self):
        return reverse("collection-wastesamples", kwargs={"pk": self.object.pk})

    def get_form(self, form_class=None):
        if self.request.method in ("POST", "PUT"):
            if self.request.POST["submit"] == "Add":
                return CollectionAddWasteSampleForm(**self.get_form_kwargs())
            if self.request.POST["submit"] == "Remove":
                return CollectionRemoveWasteSampleForm(**self.get_form_kwargs())
        else:
            return super().get_form(self.get_form_class())

    def get_context_data(self, **kwargs):
        kwargs["form_add"] = CollectionAddWasteSampleForm(**self.get_form_kwargs())
        kwargs["form_remove"] = CollectionRemoveWasteSampleForm(
            **self.get_form_kwargs()
        )
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self.request.POST["submit"] == "Add":
            self.object.samples.add(form.cleaned_data["sample"])
        if self.request.POST["submit"] == "Remove":
            self.object.samples.remove(form.cleaned_data["sample"])
        return HttpResponseRedirect(self.get_success_url())


class CollectionPredecessorsView(UserCreatedObjectUpdateView):
    template_name = "collection_predecessors.html"
    model = Collection
    form_class = CollectionAddPredecessorForm

    def get_success_url(self):
        return reverse("collection-predecessors", kwargs={"pk": self.object.pk})

    def get_form(self, form_class=None):
        if self.request.method in ("POST", "PUT"):
            if self.request.POST["submit"] == "Add":
                return CollectionAddPredecessorForm(**self.get_form_kwargs())
            if self.request.POST["submit"] == "Remove":
                return CollectionRemovePredecessorForm(**self.get_form_kwargs())
        else:
            return super().get_form(self.get_form_class())

    def get_context_data(self, **kwargs):
        kwargs["form_add"] = CollectionAddPredecessorForm(**self.get_form_kwargs())
        kwargs["form_remove"] = CollectionRemovePredecessorForm(
            **self.get_form_kwargs()
        )
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self.request.POST["submit"] == "Add":
            self.object.predecessors.add(form.cleaned_data["predecessor"])
        if self.request.POST["submit"] == "Remove":
            self.object.predecessors.remove(form.cleaned_data["predecessor"])
        return HttpResponseRedirect(self.get_success_url())


class CollectionModalArchiveView(UserCreatedObjectModalArchiveView):
    model = Collection


# ----------- Maps -----------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SoilcomDatasetVersionMixin:
    """
    Provides a stable dataset version (dv) string for caching purposes.

    The dv changes only when data visible for the current map scope changes.
    It's computed from a scope-appropriate queryset using:
    - COUNT(*)
    - MAX(lastmodified_at)
    - MIN(id)
    - MAX(id)

    The dv is then exposed to templates via context as "dataset_version".
    """

    dv_scope = None  # 'published' | 'private' | 'review' (optional override per view)

    def get_dv_scope(self):
        # Prefer explicit per-view scope, then URL param, finally default to 'published'
        return (
            getattr(self, "dv_scope", None)
            or self.request.GET.get("scope")
            or "published"
        )

    def _dv_queryset(self):
        scope = self.get_dv_scope()
        user = getattr(self.request, "user", None)
        qs = Collection.objects.all()

        if scope == "published":
            qs = qs.filter(publication_status="published")
        elif scope == "private":
            if user and user.is_authenticated and not user.is_staff:
                qs = qs.filter(owner=user)
            else:
                # Staff users on private scope: default to all (matches current staff behavior)
                qs = qs
        elif scope == "review":
            if user and user.is_authenticated and not user.is_staff:
                qs = qs.filter(Q(owner=user) | Q(publication_status="review"))
            else:
                # Staff: restrict dv to items in review to reflect the view's intent
                qs = qs.filter(publication_status="review")
        return qs

    def get_dataset_version(self) -> str:
        qs = self._dv_queryset()
        agg = qs.aggregate(
            cnt=Count("pk"),
            max_mod=Max("lastmodified_at"),
            min_id=Min("pk"),
            max_id=Max("pk"),
        )
        scope = self.get_dv_scope()
        cnt = agg.get("cnt") or 0
        max_mod = agg.get("max_mod")
        ts = int(max_mod.timestamp()) if max_mod else 0
        min_id = agg.get("min_id") or 0
        max_id = agg.get("max_id") or 0
        base = f"{scope}:{cnt}:{ts}:{min_id}:{max_id}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["dataset_version"] = self.get_dataset_version()
        return ctx


# TODO: This is out of use - Decide to fix or remove
class CatchmentSelectView(GeoDataSetFormMixin, MapMixin, TemplateView):
    template_name = "waste_collection_catchment_list.html"
    form_class = NutsAndLauCatchmentQueryForm
    region_url = reverse_lazy("data.catchment_region_geometries")
    feature_url = reverse_lazy("data.catchment-options")
    feature_summary_url = reverse_lazy("data.catchment_region_summaries")
    load_features = False
    load_catchment = True
    adjust_bounds_to_features = False
    load_region = False
    map_title = "Catchments"
    feature_layer_style = {"color": "#4061d2", "fillOpacity": 1, "stroke": False}

    def get_initial(self):
        initial = {}
        region_id = self.get_region_feature_id()
        catchment_id = self.request.GET.get("catchment")
        if catchment_id:
            catchment = CollectionCatchment.objects.get(id=catchment_id)
            initial["parent_region"] = catchment.parent_region.id
            initial["catchment"] = catchment.id
        elif region_id:
            initial["region"] = region_id
        return initial

    def get_region_feature_id(self):
        return self.request.GET.get("region")


class WasteCollectionPublishedMapView(
    SoilcomDatasetVersionMixin, GeoDataSetPublishedFilteredMapView
):
    model_name = "WasteCollection"
    template_name = "waste_collection_map.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "Household Waste Collections"
    dashboard_url = reverse_lazy("wastecollection-explorer")
    dv_scope = "published"

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "published"
        kwargs["data"] = data
        return kwargs


class WasteCollectionPrivateMapView(
    SoilcomDatasetVersionMixin, GeoDataSetPrivateFilteredMapView
):
    model_name = "WasteCollection"
    template_name = "waste_collection_map.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "My Household Waste Collections"
    dashboard_url = reverse_lazy("wastecollection-explorer")
    dv_scope = "private"

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "private"
        kwargs["data"] = data
        return kwargs


class WasteCollectionReviewMapView(
    SoilcomDatasetVersionMixin, GeoDataSetReviewFilteredMapView
):
    model = Collection
    model_name = "WasteCollection"
    template_name = "waste_collection_map.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "Collections in Review"
    dashboard_url = reverse_lazy("wastecollection-explorer")
    dv_scope = "review"

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "review"
        kwargs["data"] = data
        return kwargs


@method_decorator(xframe_options_exempt, name="dispatch")
class WasteCollectionPublishedMapIframeView(
    SoilcomDatasetVersionMixin, GeoDataSetPublishedFilteredMapView
):
    model_name = "WasteCollection"
    template_name = "waste_collection_map_iframe.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "Household Waste Collection Europe"
    dv_scope = "published"

    def post_process_map_config(self, map_config):
        map_config = super().post_process_map_config(map_config)
        map_config["applyFilterToFeatures"] = True
        return map_config

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "published"
        kwargs["data"] = data
        return kwargs


# Collection-specific review action views with cascade support
# These views extend the base review action views to add property value cascading


class CollectionSubmitForReviewView(
    CollectionReviewActionCascadeMixin, SubmitForReviewView
):
    """Submit a Collection for review and cascade to related property values."""

    pass


class CollectionWithdrawFromReviewView(
    CollectionReviewActionCascadeMixin, WithdrawFromReviewView
):
    """Withdraw a Collection from review and cascade to related property values."""

    pass


class CollectionApproveItemView(CollectionReviewActionCascadeMixin, ApproveItemView):
    """Approve a Collection and cascade to related property values."""

    pass


class CollectionRejectItemView(CollectionReviewActionCascadeMixin, RejectItemView):
    """Reject a Collection and cascade to related property values."""

    pass


# Modal versions
class CollectionSubmitForReviewModalView(
    CollectionReviewActionCascadeMixin, SubmitForReviewModalView
):
    """Modal: Submit a Collection for review with cascade."""

    pass


class CollectionWithdrawFromReviewModalView(
    CollectionReviewActionCascadeMixin, WithdrawFromReviewModalView
):
    """Modal: Withdraw a Collection from review with cascade."""

    pass


class CollectionApproveItemModalView(
    CollectionReviewActionCascadeMixin, ApproveItemModalView
):
    """Modal: Approve a Collection with cascade."""

    pass


class CollectionRejectItemModalView(
    CollectionReviewActionCascadeMixin, RejectItemModalView
):
    """Modal: Reject a Collection with cascade."""

    pass
