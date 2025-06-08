import json
from datetime import date
from urllib.parse import urlencode

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Max
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView
from django_tomselect.autocompletes import AutocompleteModelView

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
    MapMixin,
)
from utils.file_export.views import GenericUserCreatedObjectExportView
from utils.forms import DynamicTableInlineFormSetHelper, M2MInlineFormSetMixin
from utils.object_management.views import (
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalArchiveView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
)

from .filters import CollectionFilterSet, CollectorFilter, WasteFlyerFilter
from .forms import (
    AggregatedCollectionPropertyValueModelForm,
    BaseWasteFlyerUrlFormSet,
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


class CollectionDashboardView(TemplateView):
    template_name = "wastecollection_dashboard.html"


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorPublishedListView(PublishedObjectFilterView):
    model = Collector
    filterset_class = CollectorFilter
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectorPrivateListView(PrivateObjectListView):
    model = Collector
    filterset_class = CollectorFilter
    dashboard_url = reverse_lazy("wastecollection-dashboard")


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


# ----------- Collector utilities --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorAutocompleteView(AutocompleteModelView):
    model = Collector
    search_lookups = ["name__icontains"]
    ordering = ["name"]


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionSystemPublishedListView(PublishedObjectListView):
    model = CollectionSystem
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionSystemPrivateListView(PrivateObjectListView):
    model = CollectionSystem
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionSystemCreateView(UserCreatedObjectCreateView):
    form_class = CollectionSystemModelForm
    permission_required = "soilcom.add_collectionsystem"


class CollectionSystemModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CollectionSystemModalModelForm
    permission_required = "soilcom.add_collectionsystem"


class CollectionSystemDetailView(UserCreatedObjectDetailView):
    template_name = "simple_detail_card.html"
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


class WasteCategoryPublishedListView(PublishedObjectListView):
    model = WasteCategory
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class WasteCategoryPrivateListView(PrivateObjectListView):
    model = WasteCategory
    dashboard_url = reverse_lazy("wastecollection-dashboard")


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


class WasteComponentPublishedListView(PublishedObjectListView):
    model = WasteComponent
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class WasteComponentPrivateListView(PrivateObjectListView):
    model = WasteComponent
    dashboard_url = reverse_lazy("wastecollection-dashboard")


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


class FeeSystemPublishedListView(PublishedObjectListView):
    model = FeeSystem
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class FeeSystemPrivateListView(PrivateObjectListView):
    model = FeeSystem
    dashboard_url = reverse_lazy("wastecollection-dashboard")


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
    dashboard_url = reverse_lazy("wastecollection-dashboard")
    ordering = "id"


class WasteFlyerPrivateFilterView(PrivateObjectFilterView):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    dashboard_url = reverse_lazy("wastecollection-dashboard")
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


class FrequencyPublishedListView(PublishedObjectListView):
    model = CollectionFrequency
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class FrequencyPrivateListView(PrivateObjectListView):
    model = CollectionFrequency
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class FrequencyCreateView(M2MInlineFormSetMixin, UserCreatedObjectCreateView):
    form_class = CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = CollectionSeasonFormSet
    formset_form_class = CollectionSeasonForm
    formset_helper_class = CollectionSeasonFormHelper
    formset_factory_kwargs = {"extra": 0}
    relation_field_name = "seasons"
    permission_required = "soilcom.add_collectionfrequency"

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
            formset = self.get_formset()
            formset.is_valid()
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


class FrequencyAutocompleteView(AutocompleteModelView):
    model = CollectionFrequency
    search_lookups = ["name__icontains"]
    ordering = ["name"]


# ----------- CollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCreateView(UserCreatedObjectCreateView):
    form_class = CollectionPropertyValueModelForm
    permission_required = "soilcom.add_collectionpropertyvalue"


class CollectionPropertyValueDetailView(UserCreatedObjectDetailView):
    model = CollectionPropertyValue


class CollectionPropertyValueUpdateView(UserCreatedObjectUpdateView):
    model = CollectionPropertyValue
    form_class = CollectionPropertyValueModelForm


class CollectionPropertyValueModalDeleteView(UserCreatedObjectModalDeleteView):
    model = CollectionPropertyValue

    def get_success_url(self):
        return reverse("collection-detail", kwargs={"pk": self.object.collection.pk})


# ----------- AggregatedCollectionPropertyValue CRUD -------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCreateView(UserCreatedObjectCreateView):
    template_name = "soilcom/collectionpropertyvalue_form.html"
    form_class = AggregatedCollectionPropertyValueModelForm
    permission_required = "soilcom.add_aggregatedcollectionpropertyvalue"


class AggregatedCollectionPropertyValueDetailView(UserCreatedObjectDetailView):
    model = AggregatedCollectionPropertyValue


class AggregatedCollectionPropertyValueUpdateView(UserCreatedObjectUpdateView):
    template_name = "soilcom/collectionpropertyvalue_form.html"
    model = AggregatedCollectionPropertyValue
    form_class = AggregatedCollectionPropertyValueModelForm


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
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionCatchmentPrivateFilterView(PrivateObjectFilterView):
    model = CollectionCatchment
    filterset_class = CatchmentFilterSet
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionCatchmentCreateView(CatchmentCreateView):
    pass


class CollectionCatchmentDetailView(CatchmentDetailView):
    model = CollectionCatchment


class CollectionCatchmentUpdateView(CatchmentUpdateView):

    def get_success_url(self):
        return reverse("collectioncatchment-detail", kwargs={"pk": self.object.pk})


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPublishedListView(PublishedObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionPrivateListView(PrivateObjectFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    dashboard_url = reverse_lazy("wastecollection-dashboard")


class CollectionCreateView(M2MInlineFormSetMixin, UserCreatedObjectCreateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = BaseWasteFlyerUrlFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    relation_field_name = "flyers"
    permission_required = "soilcom.add_collection"

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
            formset = self.get_formset()
            formset.is_valid()
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
            formset = self.get_formset()
            formset.is_valid()
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionDetailView(UserCreatedObjectDetailView):
    model = Collection


class CollectionModalDetailView(UserCreatedObjectModalDetailView):
    model = Collection


class CollectionUpdateView(M2MInlineFormSetMixin, UserCreatedObjectUpdateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = BaseWasteFlyerUrlFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    relation_field_name = "flyers"

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
    success_url = reverse_lazy("collection-list-owned")


# ----------- Collection utils -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutocompleteView(AutocompleteModelView):
    model = Collection
    search_lookups = ["name__icontains"]
    ordering = ["name"]


class CollectionListFileExportView(GenericUserCreatedObjectExportView):
    model_label = "soilcom.Collection"


class CollectionAddPropertyValueView(CollectionPropertyValueCreateView):

    def get_initial(self):
        initial = super().get_initial()
        initial["collection"] = self.kwargs["pk"]
        return initial

    def get_success_url(self):
        return reverse("collection-detail", kwargs={"pk": self.kwargs["pk"]})


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


class WasteCollectionPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model_name = "WasteCollection"
    template_name = "waste_collection_map.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "Household Waste Collections"
    dashboard_url = reverse_lazy("wastecollection-dashboard")

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "published"
        kwargs["data"] = data
        return kwargs


class WasteCollectionPrivateMapView(GeoDataSetPrivateFilteredMapView):
    model_name = "WasteCollection"
    template_name = "waste_collection_map.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "My Household Waste Collections"
    dashboard_url = reverse_lazy("wastecollection-dashboard")

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "private"
        kwargs["data"] = data
        return kwargs


@method_decorator(xframe_options_exempt, name="dispatch")
class WasteCollectionPublishedMapIframeView(GeoDataSetPublishedFilteredMapView):
    model_name = "WasteCollection"
    template_name = "waste_collection_map_iframe.html"
    filterset_class = CollectionFilterSet
    features_layer_api_basename = "api-waste-collection"
    map_title = "Household Waste Collection Europe"

    def get_filterset_kwargs(self, filterset_class=None):
        kwargs = super().get_filterset_kwargs(filterset_class)
        data = kwargs.get("data").copy() if kwargs.get("data") else {}
        data["scope"] = "published"
        kwargs["data"] = data
        return kwargs
