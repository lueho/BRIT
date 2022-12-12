import json

from celery.result import AsyncResult
from dal.autocomplete import Select2QuerySetView
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.db.models import Max
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView
from django_filters import rest_framework as rf_filters
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

import case_studies.soilcom.tasks
from bibliography.views import (SourceCreateView, SourceModalCreateView, SourceModalDetailView, SourceUpdateView,
                                SourceModalUpdateView, SourceModalDeleteView, SourceCheckUrlView)
from distributions.models import TemporalDistribution, Timestep
from maps.forms import NutsAndLauCatchmentQueryForm
from maps.models import GeoDataset
from maps.views import CatchmentDetailView, GeoDatasetDetailView, GeoDataSetMixin, GeoDataSetFormMixin
from utils import views
from utils.forms import DynamicTableInlineFormSetHelper, M2MInlineModelFormSetMixin, M2MInlineFormSetMixin
from utils.models import Property
from utils.views import OwnedObjectCreateView, OwnedObjectUpdateView
from . import filters
from . import forms
from . import models
from . import serializers
from .filters import CollectionFilter, CollectorFilter, WasteFlyerFilter
from .models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency, Collector,
                     WasteFlyer, CollectionSeason)
from .serializers import CollectionFlatSerializer
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


class CollectorListView(views.BRITFilterView):
    model = Collector
    filterset_class = CollectorFilter
    ordering = 'name'


class CollectorCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectorModelForm
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.add_collector'


class CollectorModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectorModalModelForm
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.add_collector'


class CollectorDetailView(views.OwnedObjectDetailView):
    model = models.Collector
    permission_required = 'soilcom.view_collector'


class CollectorModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.Collector
    permission_required = 'soilcom.view_collector'


class CollectorUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.Collector
    form_class = forms.CollectorModelForm
    permission_required = 'soilcom.change_collector'


class CollectorModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.Collector
    form_class = forms.CollectorModalModelForm
    permission_required = 'soilcom.change_collector'


class CollectorModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collector
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.delete_collector'


# ----------- Collector utilities --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectorAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = models.Collector.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionSystemListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionSystemModelForm
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionSystemModalModelForm
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = models.CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionSystemUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.CollectionSystem
    form_class = forms.CollectionSystemModelForm
    permission_required = 'soilcom.change_collectionsystem'


class CollectionSystemModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.CollectionSystem
    form_class = forms.CollectionSystemModalModelForm
    permission_required = 'soilcom.change_collectionsystem'


class CollectionSystemModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.CollectionSystem
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collectionsystem-list')
    permission_required = 'soilcom.delete_collectionsystem'


# ----------- Waste Stream Category CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteCategoryListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteCategoryModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteCategoryModalModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = models.WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class WasteCategoryUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.WasteCategory
    form_class = forms.WasteCategoryModelForm
    permission_required = 'soilcom.change_wastecategory'


class WasteCategoryModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.WasteCategory
    form_class = forms.WasteCategoryModalModelForm
    permission_required = 'soilcom.change_wastecategory'


class WasteCategoryModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteCategory
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.delete_wastecategory'


# ----------- Waste Component CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteComponentListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteComponentModelForm
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteComponentModalModelForm
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = models.WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.WasteComponent
    permission_required = 'soilcom.view_wastecomponent'


class WasteComponentUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.WasteComponent
    form_class = forms.WasteComponentModelForm
    permission_required = 'soilcom.change_wastecomponent'


class WasteComponentModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.WasteComponent
    form_class = forms.WasteComponentModalModelForm
    permission_required = 'soilcom.change_wastecomponent'


class WasteComponentModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteComponent
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastecomponent-list')
    permission_required = 'soilcom.delete_wastecomponent'


# ----------- Waste Stream CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteStreamListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteStreamModelForm
    success_url = reverse_lazy('wastestream-list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteStreamModalModelForm
    success_url = reverse_lazy('wastecategory-list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = models.WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.WasteStream
    permission_required = 'soilcom.view_wastestream'


class WasteStreamUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.WasteStream
    form_class = forms.WasteStreamModelForm
    permission_required = 'soilcom.change_wastestream'


class WasteStreamModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.WasteStream
    form_class = forms.WasteStreamModalModelForm
    permission_required = 'soilcom.change_wastestream'


class WasteStreamModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteStream
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastestream-list')
    permission_required = 'soilcom.delete_wastestream'


# ----------- Waste Collection Flyer CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteFlyerListView(views.BRITFilterView):
    model = WasteFlyer
    filterset_class = WasteFlyerFilter
    ordering = 'id'


class WasteFlyerCreateView(SourceCreateView):
    form_class = forms.WasteFlyerModelForm
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.add_wasteflyer'

    def form_valid(self, form):
        form.instance.type = 'waste_flyer'
        return super().form_valid(form)


class WasteFlyerModalCreateView(SourceModalCreateView):
    form_class = forms.WasteFlyerModalModelForm
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.add_wasteflyer'

    def form_valid(self, form):
        form.instance.type = 'waste_flyer'
        return super().form_valid(form)


class WasteFlyerDetailView(views.OwnedObjectDetailView):
    model = models.WasteFlyer
    permission_required = set()


class WasteFlyerModalDetailView(SourceModalDetailView):
    template_name = 'modal_waste_flyer_detail.html'
    model = models.WasteFlyer
    permission_required = 'soilcom.view_wasteflyer'


class WasteFlyerUpdateView(SourceUpdateView):
    model = models.WasteFlyer
    form_class = forms.WasteFlyerModelForm
    permission_required = 'soilcom.change_wasteflyer'


class WasteFlyerModalUpdateView(SourceModalUpdateView):
    model = models.WasteFlyer
    form_class = forms.WasteFlyerModalModelForm
    permission_required = 'soilcom.change_wasteflyer'


class WasteFlyerModalDeleteView(SourceModalDeleteView):
    success_url = reverse_lazy('wasteflyer-list')
    permission_required = 'soilcom.delete_wasteflyer'


# ----------- Waste Collection Flyer utils -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerCheckUrlView(SourceCheckUrlView):
    model = models.WasteFlyer
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
    model = models.WasteFlyer
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

class FrequencyListView(views.OwnedObjectListView):
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyCreateView(M2MInlineFormSetMixin, OwnedObjectCreateView):
    form_class = forms.CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = forms.CollectionSeasonFormSet
    formset_form_class = forms.CollectionSeasonForm
    formset_helper_class = forms.CollectionSeasonFormHelper
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


class FrequencyDetailView(views.OwnedObjectDetailView):
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyUpdateView(M2MInlineFormSetMixin, OwnedObjectUpdateView):
    model = CollectionFrequency
    form_class = forms.CollectionFrequencyModelForm
    formset_model = CollectionSeason
    formset_class = forms.CollectionSeasonFormSet
    formset_form_class = forms.CollectionSeasonForm
    formset_helper_class = forms.CollectionSeasonFormHelper
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


class FrequencyModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.CollectionFrequency
    form_class = forms.CollectionFrequencyModalModelForm
    permission_required = 'soilcom.change_collectionfrequency'


class FrequencyModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.CollectionFrequency
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collectionfrequency-list')
    permission_required = 'soilcom.delete_collectionfrequency'


# ----------- Frequency Utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FrequencyAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = models.CollectionFrequency.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- CollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionPropertyValueModelForm
    permission_required = 'soilcom.add_collectionpropertyvalue'


class CollectionPropertyValueDetailView(views.OwnedObjectDetailView):
    model = models.CollectionPropertyValue
    permission_required = set()


class CollectionPropertyValueUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.CollectionPropertyValue
    form_class = forms.CollectionPropertyValueModelForm
    permission_required = 'soilcom.change_collectionpropertyvalue'


class CollectionPropertyValueModalDeleteView(views.OwnedObjectModalDeleteView):
    model = models.CollectionPropertyValue
    success_message = 'Successfully deleted.'
    permission_required = 'soilcom.delete_collectionpropertyvalue'

    def get_success_url(self):
        return reverse('collection-detail', kwargs={'pk': self.object.collection.pk})


# ----------- AggregatedCollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.AggregatedCollectionPropertyValueModelForm
    permission_required = 'soilcom.add_aggregatedcollectionpropertyvalue'


class AggregatedCollectionPropertyValueDetailView(views.OwnedObjectDetailView):
    model = models.AggregatedCollectionPropertyValue
    permission_required = set()


class AggregatedCollectionPropertyValueUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.AggregatedCollectionPropertyValue
    form_class = forms.AggregatedCollectionPropertyValueModelForm
    permission_required = 'soilcom.change_aggregatedcollectionpropertyvalue'


class AggregatedCollectionPropertyValueModalDeleteView(views.OwnedObjectModalDeleteView):
    model = models.AggregatedCollectionPropertyValue
    success_message = 'Successfully deleted.'
    permission_required = 'soilcom.delete_aggregatedcollectionpropertyvalue'

    def get_success_url(self):
        return reverse('collection-list')


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionListView(views.BRITFilterView):
    model = Collection
    filterset_class = CollectionFilter
    ordering = 'name'


class CollectionCreateView(M2MInlineFormSetMixin, views.OwnedObjectCreateView):
    template_name = 'form_and_formset.html'
    model = Collection
    form_class = forms.CollectionModelForm
    formset_model = WasteFlyer
    formset_class = forms.BaseWasteFlyerUrlFormSet
    formset_form_class = forms.WasteFlyerModelForm
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
            initial['collector'] = models.Collector.objects.get(id=self.request.GET.get('collector'))
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
    model = models.Collection

    def get_initial(self):
        initial = model_to_dict(self.object)
        initial.update({
            'waste_category': self.object.waste_stream.category.id,
            'allowed_materials': [mat.id for mat in self.object.waste_stream.allowed_materials.all()]
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


class CollectionDetailView(views.OwnedObjectDetailView):
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionUpdateView(M2MInlineFormSetMixin, views.OwnedObjectUpdateView):
    model = models.Collection
    form_class = forms.CollectionModelForm
    formset_model = WasteFlyer
    formset_class = forms.BaseWasteFlyerUrlFormSet
    formset_form_class = forms.WasteFlyerModelForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    relation_field_name = 'flyers'
    permission_required = 'soilcom.change_collection'
    template_name = 'collection_form_card.html'

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({'owner': self.request.user})
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'waste_category': self.object.waste_stream.category.id,
            'allowed_materials': [mat.id for mat in self.object.waste_stream.allowed_materials.all()],
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


class CollectionModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collection
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collection-list')
    permission_required = 'soilcom.delete_collection'


# ----------- Collection utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = models.Collection.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class CollectionAddPropertyValueView(CollectionPropertyValueCreateView):

    def get_initial(self):
        initial = super().get_initial()
        prop, _ = Property.objects.get_or_create(
            name='specific waste generation',
            defaults={'unit': 'kg/(cap.*a)'}
        )
        initial['property'] = prop.pk
        initial['collection'] = self.kwargs['pk']
        return initial

    def get_success_url(self):
        return reverse('collection-detail', kwargs={'pk': self.kwargs['pk']})


class CollectionCatchmentAddAggregatedPropertyView(AggregatedCollectionPropertyValueCreateView):

    def get_initial(self):
        initial = super().get_initial()
        catchment = CollectionCatchment.objects.get(pk=self.kwargs.get('pk'))
        initial['collections'] = catchment.downstream_collections
        prop, _ = Property.objects.get_or_create(
            name='specific waste generation',
            defaults={'unit': 'kg/(cap.*a)'}
        )
        initial['property'] = prop
        return initial


class SelectNewlyCreatedObjectModelSelectOptionsView(views.OwnedObjectModelSelectOptionsView):

    def get_selected_object(self):
        # TODO: Improve this by adding owner to
        created_at = self.model.objects.aggregate(max_created_at=Max('created_at'))['max_created_at']
        return self.model.objects.get(created_at=created_at)


class CollectorOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = models.Collector
    permission_required = 'soilcom.view_collector'


class CollectionSystemOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = models.CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'


class CollectionFrequencyOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = models.CollectionFrequency
    permission_required = 'soilcom.view_collectionfrequency'


class WasteCategoryOptions(SelectNewlyCreatedObjectModelSelectOptionsView):
    model = models.WasteCategory
    permission_required = 'soilcom.view_wastecategory'


class CollectionWasteSamplesView(views.OwnedObjectUpdateView):
    template_name = 'collection_samples.html'
    model = Collection
    form_class = forms.CollectionAddWasteSampleForm
    permission_required = 'soilcom.change_collection'

    def get_success_url(self):
        return reverse('collection-wastesamples', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        if self.request.method in ('POST', 'PUT'):
            if self.request.POST['submit'] == 'Add':
                return forms.CollectionAddWasteSampleForm(**self.get_form_kwargs())
            if self.request.POST['submit'] == 'Remove':
                return forms.CollectionRemoveWasteSampleForm(**self.get_form_kwargs())
        else:
            return super().get_form(self.get_form_class())

    def get_context_data(self, **kwargs):
        kwargs['form_add'] = forms.CollectionAddWasteSampleForm(**self.get_form_kwargs())
        kwargs['form_remove'] = forms.CollectionRemoveWasteSampleForm(**self.get_form_kwargs())
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self.request.POST['submit'] == 'Add':
            self.object.samples.add(form.cleaned_data['sample'])
        if self.request.POST['submit'] == 'Remove':
            self.object.samples.remove(form.cleaned_data['sample'])
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
    adjust_bounds_to_features = False
    load_region = False
    map_title = 'Catchments'
    marker_style = {
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


class WasteCollectionMapView(GeoDatasetDetailView):
    template_name = 'waste_collection_map.html'
    feature_url = reverse_lazy('collection-geometry-api')
    feature_summary_url = reverse_lazy('collection-summary-api')
    filterset_class = filters.CollectionFilter
    load_features = False
    adjust_bounds_to_features = True
    load_region = False
    marker_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'stroke': False
    }

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'collection_system': self.request.GET.getlist('collection_system'),
            'waste_category': self.request.GET.getlist('waste_category'),
            'countries': self.request.GET.getlist('countries'),
            'allowed_materials': self.request.GET.getlist('allowed_materials')
        })
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = models.Collection.objects.all()
        filterset = self.filterset_class(self.request.GET, queryset=queryset)
        context['filter'] = filterset
        return context

    def get_object(self, **kwargs):
        self.kwargs.update({'pk': GeoDataset.objects.get(model_name='WasteCollection').pk})
        return super().get_object(**kwargs)


# ----------- API ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionGeometryAPI(GenericAPIView):
    queryset = models.Collection.objects.all()
    serializer_class = serializers.WasteCollectionGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = filters.CollectionFilter
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
    filterset_class = filters.CollectionFilter


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
        obj = models.Collection.objects.get(id=request.query_params.get('pk'))
        objs = models.Collection.objects.filter(catchment=obj.catchment)
        serializer = serializers.CollectionModelSerializer(
            objs,
            many=True,
            field_labels_as_keys=True,
            context={'request': request})
        return Response({'summaries': serializer.data})
