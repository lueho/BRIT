import json
from datetime import date

from celery.result import AsyncResult
from dal.autocomplete import Select2QuerySetView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Max
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView
from django_filters import rest_framework as rf_filters
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

import case_studies.soilcom.tasks
from bibliography.views import (SourceCheckUrlView, SourceCreateView, SourceModalCreateView, SourceModalDeleteView,
                                SourceModalDetailView, SourceModalUpdateView, SourceUpdateView)
from maps.forms import NutsAndLauCatchmentQueryForm
from maps.views import CatchmentDetailView, GeoDataSetDetailView, GeoDataSetFormMixin, GeoDataSetMixin
from utils.forms import DynamicTableInlineFormSetHelper, M2MInlineFormSetMixin
from utils.views import (BRITFilterView, OwnedObjectCreateView, OwnedObjectDetailView, OwnedObjectListView,
                         OwnedObjectModalCreateView, OwnedObjectModalDeleteView, OwnedObjectModalDetailView,
                         OwnedObjectModalUpdateView, OwnedObjectModelSelectOptionsView, OwnedObjectUpdateView)
from .filters import CollectionFilterSet, CollectorFilter, WasteFlyerFilter
from .forms import (AggregatedCollectionPropertyValueModelForm, BaseWasteFlyerUrlFormSet, CollectionAddPredecessorForm,
                    CollectionAddWasteSampleForm, CollectionFrequencyModalModelForm, CollectionFrequencyModelForm,
                    CollectionModelForm, CollectionPropertyValueModelForm, CollectionRemovePredecessorForm,
                    CollectionRemoveWasteSampleForm, CollectionSeasonForm, CollectionSeasonFormHelper,
                    CollectionSeasonFormSet, CollectionSystemModalModelForm, CollectionSystemModelForm,
                    CollectorModalModelForm, CollectorModelForm, WasteCategoryModalModelForm, WasteCategoryModelForm,
                    WasteComponentModalModelForm, WasteComponentModelForm, WasteFlyerModalModelForm,
                    WasteFlyerModelForm, WasteStreamModalModelForm, WasteStreamModelForm)
from .models import (AggregatedCollectionPropertyValue, Collection, CollectionCatchment, CollectionCountOptions,
                     CollectionFrequency,
                     CollectionPropertyValue, CollectionSeason,
                     CollectionSystem, Collector, WasteCategory, WasteComponent, WasteFlyer, WasteStream)
from .serializers import CollectionFlatSerializer, CollectionModelSerializer, WasteCollectionGeometrySerializer
from .tasks import check_wasteflyer_urls


class CollectionHomeView(PermissionRequiredMixin, TemplateView):
    template_name = 'waste_collection_home.html'
    permission_required = 'soilcom.view_collection'


# ----------- CollectionCatchment CRUD ---------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCatchmentDetailView(CatchmentDetailView):
    model = CollectionCatchment
    permission_required = set()


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorListView(BRITFilterView):
    model = Collector
    filterset_class = CollectorFilter
    ordering = 'name'


class CollectorCreateView(OwnedObjectCreateView):
    form_class = CollectorModelForm
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.add_collector'


class CollectorModalCreateView(OwnedObjectModalCreateView):
    form_class = CollectorModalModelForm
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.add_collector'


class CollectorDetailView(OwnedObjectDetailView):
    model = Collector
    permission_required = 'soilcom.view_collector'


class CollectorModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Collector
    permission_required = 'soilcom.view_collector'


class CollectorUpdateView(OwnedObjectUpdateView):
    model = Collector
    form_class = CollectorModelForm
    permission_required = 'soilcom.change_collector'


class CollectorModalUpdateView(OwnedObjectModalUpdateView):
    model = Collector
    form_class = CollectorModalModelForm
    permission_required = 'soilcom.change_collector'


class CollectorModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Collector
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.delete_collector'


# ----------- Collector utilities --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectorAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = Collector.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionSystemListView(OwnedObjectListView):
    model = CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemCreateView(OwnedObjectCreateView):
    form_class = CollectionSystemModelForm
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemModalCreateView(OwnedObjectModalCreateView):
    form_class = CollectionSystemModalModelForm
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemUpdateView(OwnedObjectUpdateView):
    model = CollectionSystem
    form_class = CollectionSystemModelForm
    permission_required = 'soilcom.change_collectionsystem'


class CollectionSystemModalUpdateView(OwnedObjectModalUpdateView):
    model = CollectionSystem
    form_class = CollectionSystemModalModelForm
    permission_required = 'soilcom.change_collectionsystem'


class CollectionSystemModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = CollectionSystem
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.delete_collectionsystem'


# ----------- Waste Stream Category CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteCategoryListView(OwnedObjectListView):
    model = WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryCreateView(OwnedObjectCreateView):
    form_class = WasteCategoryModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryModalCreateView(OwnedObjectModalCreateView):
    form_class = WasteCategoryModalModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryUpdateView(OwnedObjectUpdateView):
    model = WasteCategory
    form_class = WasteCategoryModelForm
    permission_required = 'soilcom.change_wastecategory'


class WasteCategoryModalUpdateView(OwnedObjectModalUpdateView):
    model = WasteCategory
    form_class = WasteCategoryModalModelForm
    permission_required = 'soilcom.change_wastecategory'


class WasteCategoryModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = WasteCategory
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.delete_wastecategory'


# ----------- Waste Component CRUD -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteComponentListView(OwnedObjectListView):
    model = WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentCreateView(OwnedObjectCreateView):
    form_class = WasteComponentModelForm
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentModalCreateView(OwnedObjectModalCreateView):
    form_class = WasteComponentModalModelForm
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentUpdateView(OwnedObjectUpdateView):
    model = WasteComponent
    form_class = WasteComponentModelForm
    permission_required = 'soilcom.change_wastecomponent'


class WasteComponentModalUpdateView(OwnedObjectModalUpdateView):
    model = WasteComponent
    form_class = WasteComponentModalModelForm
    permission_required = 'soilcom.change_wastecomponent'


class WasteComponentModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = WasteComponent
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.delete_wastecomponent'


# ----------- Waste Stream CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteStreamListView(OwnedObjectListView):
    model = WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamCreateView(OwnedObjectCreateView):
    form_class = WasteStreamModelForm
    success_url = reverse_lazy('wastestream-list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamModalCreateView(OwnedObjectModalCreateView):
    form_class = WasteStreamModalModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamUpdateView(OwnedObjectUpdateView):
    model = WasteStream
    form_class = WasteStreamModelForm
    permission_required = 'soilcom.change_wastestream'


class WasteStreamModalUpdateView(OwnedObjectModalUpdateView):
    model = WasteStream
    form_class = WasteStreamModalModelForm
    permission_required = 'soilcom.change_wastestream'


class WasteStreamModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = WasteStream
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastestream-list')
    permission_required = 'soilcom.delete_wastestream'


# ----------- Waste Collection Flyer CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteFlyerListView(BRITFilterView):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    ordering = 'id'


class WasteFlyerCreateView(SourceCreateView):
    form_class = WasteFlyerModelForm
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.add_wasteflyer'

    def form_valid(self, form):
        form.instance.type = 'waste_flyer'
        return super().form_valid(form)


class WasteFlyerModalCreateView(SourceModalCreateView):
    form_class = WasteFlyerModalModelForm
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.add_wasteflyer'

    def form_valid(self, form):
        form.instance.type = 'waste_flyer'
        return super().form_valid(form)


class WasteFlyerDetailView(OwnedObjectDetailView):
    model = WasteFlyer
    permission_required = set()


class WasteFlyerModalDetailView(SourceModalDetailView):
    template_name = 'modal_waste_flyer_detail.html'
    model = WasteFlyer
    permission_required = 'soilcom.view_wasteflyer'


class WasteFlyerUpdateView(SourceUpdateView):
    model = WasteFlyer
    form_class = WasteFlyerModelForm
    permission_required = 'soilcom.change_wasteflyer'


class WasteFlyerModalUpdateView(SourceModalUpdateView):
    model = WasteFlyer
    form_class = WasteFlyerModalModelForm
    permission_required = 'soilcom.change_wasteflyer'


class WasteFlyerModalDeleteView(SourceModalDeleteView):
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.delete_wasteflyer'


# ----------- Waste Collection Flyer utils -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerCheckUrlView(SourceCheckUrlView):
    model = WasteFlyer
    permission_required = 'soilcom.change_wasteflyer'


class WasteFlyerCheckUrlProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class WasteFlyerListCheckUrlsView(PermissionRequiredMixin, View):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    permission_required = 'soilcom.change_wasteflyer'

    @staticmethod
    def get(request, *args, **kwargs):
        params = request.GET.copy()
        params.pop('csrfmiddlewaretoken', None)
        params.pop('page', None)
        task = check_wasteflyer_urls.delay(params)
        callback_id = task.get()[0][0]
        response_data = {
            'task_id': callback_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class WasteFlyerListCheckUrlsProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


# ----------- Frequency CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class FrequencyListView(OwnedObjectListView):
    model = CollectionFrequency
    permission_required = set()


class FrequencyCreateView(M2MInlineFormSetMixin, OwnedObjectCreateView):
    form_class = CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = CollectionSeasonFormSet
    formset_form_class = CollectionSeasonForm
    formset_helper_class = CollectionSeasonFormHelper
    formset_factory_kwargs = {'extra': 0}
    relation_field_name = 'seasons'
    permission_required = 'soilcom.add_collectionfrequency'

    def get_formset_initial(self):
        return list(CollectionSeason.objects.filter(
            distribution__name='Months of the year',
            first_timestep__name='January',
            last_timestep__name='December'
        ).values('distribution', 'first_timestep', 'last_timestep'))

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


class FrequencyDetailView(OwnedObjectDetailView):
    model = CollectionFrequency
    permission_required = set()


class FrequencyModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = CollectionFrequency
    permission_required = set()


class FrequencyUpdateView(M2MInlineFormSetMixin, OwnedObjectUpdateView):
    model = CollectionFrequency
    form_class = CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = CollectionSeasonFormSet
    formset_form_class = CollectionSeasonForm
    formset_helper_class = CollectionSeasonFormHelper
    formset_factory_kwargs = {'extra': 0}
    relation_field_name = 'seasons'
    permission_required = 'soilcom.change_collectionfrequency'

    def get_formset_initial(self):
        initial = []
        for season in self.object.seasons.all():
            options = CollectionCountOptions.objects.get(frequency=self.object, season=season)
            initial.append({
                'distribution': season.distribution,
                'first_timestep': season.first_timestep,
                'last_timestep': season.last_timestep,
                'standard': options.standard,
                'option_1': options.option_1,
                'option_2': options.option_2,
                'option_3': options.option_3,
            })
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


class FrequencyModalUpdateView(OwnedObjectModalUpdateView):
    model = CollectionFrequency
    form_class = CollectionFrequencyModalModelForm
    permission_required = 'soilcom.change_collectionfrequency'


class FrequencyModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = CollectionFrequency
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collectionfrequency-list')
    permission_required = 'soilcom.delete_collectionfrequency'


# ----------- Frequency Utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FrequencyAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = CollectionFrequency.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- CollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCreateView(OwnedObjectCreateView):
    model = CollectionPropertyValue
    form_class = CollectionPropertyValueModelForm
    permission_required = 'soilcom.add_collectionpropertyvalue'


class CollectionPropertyValueDetailView(OwnedObjectDetailView):
    model = CollectionPropertyValue
    permission_required = set()


class CollectionPropertyValueUpdateView(OwnedObjectUpdateView):
    model = CollectionPropertyValue
    form_class = CollectionPropertyValueModelForm
    permission_required = 'soilcom.change_collectionpropertyvalue'


class CollectionPropertyValueModalDeleteView(OwnedObjectModalDeleteView):
    model = CollectionPropertyValue
    success_message = 'Successfully deleted.'
    permission_required = 'soilcom.delete_collectionpropertyvalue'

    def get_success_url(self):
        return reverse('collection-detail', kwargs={'pk': self.object.collection.pk})


# ----------- AggregatedCollectionPropertyValue CRUD -------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCreateView(OwnedObjectCreateView):
    template_name = 'soilcom/collectionpropertyvalue_form.html'
    form_class = AggregatedCollectionPropertyValueModelForm
    permission_required = 'soilcom.add_aggregatedcollectionpropertyvalue'


class AggregatedCollectionPropertyValueDetailView(OwnedObjectDetailView):
    model = AggregatedCollectionPropertyValue
    permission_required = set()


class AggregatedCollectionPropertyValueUpdateView(OwnedObjectUpdateView):
    template_name = 'soilcom/collectionpropertyvalue_form.html'
    model = AggregatedCollectionPropertyValue
    form_class = AggregatedCollectionPropertyValueModelForm
    permission_required = 'soilcom.change_aggregatedcollectionpropertyvalue'


class AggregatedCollectionPropertyValueModalDeleteView(OwnedObjectModalDeleteView):
    model = AggregatedCollectionPropertyValue
    success_message = 'Successfully deleted.'
    permission_required = 'soilcom.delete_aggregatedcollectionpropertyvalue'

    def get_success_url(self):
        return reverse('collection-list')


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionCurrentListView(BRITFilterView):
    model = Collection
    filterset_class = CollectionFilterSet
    ordering = 'name'

    def get_queryset(self):
        queryset = super().get_queryset()

        # Check if it's a GET request and no query parameters are present
        # This implies that the user has just opened the page and no filtering has been applied yet.
        if self.request.method == 'GET' and not self.request.GET:
            queryset = queryset.currently_valid()

        return queryset


class CollectionCreateView(M2MInlineFormSetMixin, OwnedObjectCreateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = BaseWasteFlyerUrlFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    relation_field_name = 'flyers'
    permission_required = 'soilcom.add_collection'

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'owner': self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if 'region_id' in self.request.GET:
            region_id = self.request.GET.get('region_id')
            catchment = CollectionCatchment.objects.get(id=region_id)
            initial['catchment'] = catchment
        if 'collector' in self.request.GET:
            initial['collector'] = Collector.objects.get(id=self.request.GET.get('collector'))
        initial['valid_from'] = date.today()
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
    model = Collection

    def get_initial(self):
        initial = model_to_dict(self.object)
        initial.update({
            'waste_category': self.object.waste_stream.category.id,
            'allowed_materials': [mat.id for mat in self.object.waste_stream.allowed_materials.all()],
            'forbidden_materials': [mat.id for mat in self.object.waste_stream.forbidden_materials.all()],
        })
        # Prevent the ModelFormMixin from passing the original instance into the ModelForm by removing self.object.
        # That way, a new instance is created, instead.
        self.object = None
        return initial

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


class CollectionCreateNewVersionView(CollectionCopyView):
    predecessor = None

    def get_initial(self):
        initial = model_to_dict(self.object)
        initial.update({
            'waste_category': self.object.waste_stream.category.id,
            'allowed_materials': [mat.id for mat in self.object.waste_stream.allowed_materials.all()],
            'forbidden_materials': [mat.id for mat in self.object.waste_stream.forbidden_materials.all()],
        })
        # Prevent the ModelFormMixin from passing the original instance into the ModelForm by removing self.object.
        # That way, a new instance is created, instead.
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


class CollectionDetailView(OwnedObjectDetailView):
    model = Collection
    permission_required = set()


class CollectionModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Collection
    permission_required = 'soilcom.view_collection'


class CollectionUpdateView(M2MInlineFormSetMixin, OwnedObjectUpdateView):
    model = Collection
    form_class = CollectionModelForm
    formset_model = WasteFlyer
    formset_class = BaseWasteFlyerUrlFormSet
    formset_form_class = WasteFlyerModelForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    relation_field_name = 'flyers'
    permission_required = 'soilcom.change_collection'

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({'owner': self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'waste_category': self.object.waste_stream.category.id,
            'allowed_materials': [mat.id for mat in self.object.waste_stream.allowed_materials.all()],
            'forbidden_materials': [mat.id for mat in self.object.waste_stream.forbidden_materials.all()],
        })
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


class CollectionModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Collection
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collection-list')
    permission_required = 'soilcom.delete_collection'


# ----------- Collection utils -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = Collection.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class CollectionAddPropertyValueView(CollectionPropertyValueCreateView):

    def get_initial(self):
        initial = super().get_initial()
        initial['collection'] = self.kwargs['pk']
        return initial

    def get_success_url(self):
        return reverse('collection-detail', kwargs={'pk': self.kwargs['pk']})


class CollectionCatchmentAddAggregatedPropertyView(AggregatedCollectionPropertyValueCreateView):

    def get_initial(self):
        initial = super().get_initial()
        catchment = CollectionCatchment.objects.get(pk=self.kwargs.get('pk'))
        initial['collections'] = catchment.downstream_collections
        return initial


class SelectNewlyCreatedObjectModelSelectOptionsView(OwnedObjectModelSelectOptionsView):

    def get_selected_object(self):
        # TODO: Improve this by adding owner to
        created_at = self.model.objects.aggregate(max_created_at=Max('created_at'))['max_created_at']
        return self.model.objects.get(created_at=created_at)


class CollectorOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = Collector
    permission_required = 'soilcom.view_collector'


class CollectionSystemOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionFrequencyOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = CollectionFrequency
    permission_required = 'soilcom.view_collectionfrequency'


class WasteCategoryOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class CollectionWasteSamplesView(OwnedObjectUpdateView):
    template_name = 'collection_samples.html'
    model = Collection
    form_class = CollectionAddWasteSampleForm
    permission_required = 'soilcom.change_collection'

    def get_success_url(self):
        return reverse('collection-wastesamples', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        if self.request.method in ('POST', 'PUT'):
            if self.request.POST['submit'] == 'Add':
                return CollectionAddWasteSampleForm(**self.get_form_kwargs())
            if self.request.POST['submit'] == 'Remove':
                return CollectionRemoveWasteSampleForm(**self.get_form_kwargs())
        else:
            return super().get_form(self.get_form_class())

    def get_context_data(self, **kwargs):
        kwargs['form_add'] = CollectionAddWasteSampleForm(**self.get_form_kwargs())
        kwargs['form_remove'] = CollectionRemoveWasteSampleForm(**self.get_form_kwargs())
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self.request.POST['submit'] == 'Add':
            self.object.samples.add(form.cleaned_data['sample'])
        if self.request.POST['submit'] == 'Remove':
            self.object.samples.remove(form.cleaned_data['sample'])
        return HttpResponseRedirect(self.get_success_url())


class CollectionPredecessorsView(OwnedObjectUpdateView):
    template_name = 'collection_predecessors.html'
    model = Collection
    form_class = CollectionAddPredecessorForm
    permission_required = 'soilcom.change_collection'

    def get_success_url(self):
        return reverse('collection-predecessors', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        if self.request.method in ('POST', 'PUT'):
            if self.request.POST['submit'] == 'Add':
                return CollectionAddPredecessorForm(**self.get_form_kwargs())
            if self.request.POST['submit'] == 'Remove':
                return CollectionRemovePredecessorForm(**self.get_form_kwargs())
        else:
            return super().get_form(self.get_form_class())

    def get_context_data(self, **kwargs):
        kwargs['form_add'] = CollectionAddPredecessorForm(**self.get_form_kwargs())
        kwargs['form_remove'] = CollectionRemovePredecessorForm(**self.get_form_kwargs())
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self.request.POST['submit'] == 'Add':
            self.object.predecessors.add(form.cleaned_data['predecessor'])
        if self.request.POST['submit'] == 'Remove':
            self.object.predecessors.remove(form.cleaned_data['predecessor'])
        return HttpResponseRedirect(self.get_success_url())


# ----------- Maps -----------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentSelectView(GeoDataSetFormMixin, GeoDataSetMixin, TemplateView):
    template_name = 'waste_collection_catchment_list.html'
    form_class = NutsAndLauCatchmentQueryForm
    region_url = reverse_lazy('data.catchment_region_geometries')
    feature_url = reverse_lazy('data.catchment-options')
    feature_summary_url = reverse_lazy('data.catchment_region_summaries')
    load_features = False
    load_catchment = True
    adjust_bounds_to_features = False
    load_region = False
    map_title = 'Catchments'
    feature_layer_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'stroke': False
    }

    def get_initial(self):
        initial = {}
        region_id = self.get_region_id()
        catchment_id = self.request.GET.get('catchment')
        if catchment_id:
            catchment = CollectionCatchment.objects.get(id=catchment_id)
            initial['parent_region'] = catchment.parent_region.id
            initial['catchment'] = catchment.id
        elif region_id:
            initial['region'] = region_id
        return initial

    def get_region_id(self):
        return self.request.GET.get('region')


class WasteCollectionMapView(GeoDataSetDetailView):
    model_name = 'WasteCollection'
    template_name = 'waste_collection_map.html'
    filterset_class = CollectionFilterSet
    map_title = 'Household Waste Collection Europe'
    load_region = False
    load_catchment = False
    load_features = True
    feature_url = reverse_lazy('collection-geometry-api')
    apply_filter_to_features = True
    adjust_bounds_to_features = False
    feature_summary_url = reverse_lazy('collection-summary-api')


# ----------- API ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionGeometryAPI(GenericAPIView):
    queryset = Collection.objects.select_related('catchment', 'waste_stream__category', 'collection_system')
    serializer_class = WasteCollectionGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = CollectionFilterSet
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = {'geoJson': serializer.data}
        return JsonResponse(data)


class CollectionViewSet(ReadOnlyModelViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = CollectionFilterSet


class CollectionListFileExportView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, *args, **kwargs):
        params = dict(request.GET)
        file_format = params.pop('format', 'csv')[0]
        params.pop('page', None)
        task = case_studies.soilcom.tasks.export_collections_to_file.delay(file_format, params)
        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class CollectionListFileExportProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class CollectionSummaryAPI(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        serializer = CollectionModelSerializer(
            Collection.objects.filter(id=request.query_params.get('id')),
            many=True,
            field_labels_as_keys=True,
            context={'request': request})
        return Response({'summaries': serializer.data})
