import csv

from dal import autocomplete
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Max
from django.forms import modelformset_factory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django_filters import rest_framework as rf_filters
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView, Response

from bibliography.views import (SourceListView,
                                SourceCreateView,
                                SourceModalCreateView,
                                SourceDetailView,
                                SourceModalDetailView,
                                SourceUpdateView,
                                SourceModalUpdateView,
                                SourceModalDeleteView)
from brit import views
from maps.forms import NutsAndLauCatchmentQueryForm
from maps.models import Catchment, GeoDataset
from maps.views import GeoDatasetDetailView, GeoDataSetMixin, GeoDataSetFormMixin
from . import filters
from . import forms
from . import models
from . import serializers


class CollectionHomeView(PermissionRequiredMixin, TemplateView):
    template_name = 'waste_collection_home.html'
    permission_required = 'soilcom.view_collection'


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectorListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.Collector
    permission_required = 'soilcom.view_collector'


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


class CollectorModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collector
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collector-list')
    permission_required = 'soilcom.delete_collector'


# ----------- Collector utilities --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectorAutoCompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = models.Collector.objects.all()
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


class CollectionSystemModalDeleteView(views.OwnedObjectDeleteView):
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


class WasteCategoryModalDeleteView(views.OwnedObjectDeleteView):
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


class WasteComponentModalDeleteView(views.OwnedObjectDeleteView):
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


class WasteStreamModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteStream
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('wastestream-list')
    permission_required = 'soilcom.delete_wastestream'


# ----------- Waste Collection Flyer CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteFlyerListView(SourceListView):
    template_name = 'waste_flyers_list.html'
    model = models.WasteFlyer
    queryset = models.WasteFlyer.objects.all().order_by('abbreviation')
    permission_required = 'soilcom.view_wasteflyer'


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


class WasteFlyerDetailView(SourceDetailView):
    template_name = 'waste_flyer_detail.html'
    model = models.WasteFlyer
    permission_required = 'soilcom.view_wasteflyer'


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


# ----------- Frequency CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class FrequencyListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionFrequencyModelForm
    success_url = reverse_lazy('collectionfrequency-list')
    permission_required = 'soilcom.add_collectionfrequency'


class FrequencyModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionFrequencyModalModelForm
    success_url = reverse_lazy('collectionfrequency-list')
    permission_required = 'soilcom.add_collectionfrequency'


class FrequencyDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.CollectionFrequency
    permission_required = set()


class FrequencyUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.CollectionFrequency
    form_class = forms.CollectionFrequencyModelForm
    permission_required = 'soilcom.change_collectionfrequency'


class FrequencyModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.CollectionFrequency
    form_class = forms.CollectionFrequencyModalModelForm
    permission_required = 'soilcom.change_collectionfrequency'


class FrequencyModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.CollectionFrequency
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collectionfrequency-list')
    permission_required = 'soilcom.delete_collectionfrequency'


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionListView(views.OwnedObjectListView):
    template_name = 'collection_list.html'
    model = models.Collection
    queryset = models.Collection.objects.order_by('id')
    filterset_class = filters.CollectionFilter
    filterset = None
    permission_required = set()

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filterset
        return context


class ModelFormAndModelFormSetMixin:
    object = None
    formset_model = None
    formset_class = None
    formset_form_class = None

    def get_formset(self, **kwargs):
        FormSet = modelformset_factory(
            self.formset_model,
            form=self.formset_form_class,
            formset=self.formset_class
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'data': self.request.POST.copy()})
        return kwargs

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        kwargs['formset_helper'] = forms.FormSetHelper()
        return super().get_context_data(**kwargs)


class CollectionCreateView(ModelFormAndModelFormSetMixin, views.OwnedObjectCreateView):
    template_name = 'collection_form_card.html'
    form_class = forms.CollectionModelForm
    formset_model = models.WasteFlyer
    formset_class = forms.WasteFlyerModelFormSet
    formset_form_class = forms.WasteFlyerModelForm
    permission_required = 'soilcom.add_collection'

    def get_formset_kwargs(self, **kwargs):
        if 'queryset' not in kwargs:
            kwargs.update({
                'queryset': self.formset_model.objects.none()
            })
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if 'region_id' in self.request.GET:
            region_id = self.request.GET.get('region_id')
            catchment = Catchment.objects.get(id=region_id)
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
            for form in formset:
                form.instance.owner = request.user
            flyers = formset.save()
            # The save() method of formset only returns instances that have been changed or newly created. We want
            # to keep the unchanged previously existing flyers as well.
            for form in formset.initial_forms:
                if form.instance.pk and not form.has_changed():
                    flyers.append(form.instance)
            self.object.flyers.set(list(flyers))
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionCopyView(CollectionCreateView):
    model = models.Collection
    original_object = None

    def get_original_object(self):
        return self.model.objects.get(pk=self.kwargs.get('pk'))

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({
            'parent_object': self.original_object,
            'queryset': self.formset_model.objects.filter(collections=self.original_object)
        })
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = {}
        if self.original_object.catchment:
            initial['catchment'] = self.original_object.catchment
        if self.original_object.collector:
            initial['collector'] = self.original_object.collector
        if self.original_object.collection_system:
            initial['collection_system'] = self.original_object.collection_system
        if self.original_object.waste_stream:
            if self.original_object.waste_stream.category:
                initial['waste_category'] = self.original_object.waste_stream.category
            if self.original_object.waste_stream.allowed_materials.exists():
                initial['allowed_materials'] = self.original_object.waste_stream.allowed_materials.all()
        if self.original_object.connection_rate:
            initial['connection_rate'] = self.original_object.connection_rate * 100
        if self.original_object.connection_rate_year:
            initial['connection_rate_year'] = self.original_object.connection_rate_year
        if self.original_object.frequency:
            initial['frequency'] = self.original_object.frequency
        if self.original_object.description:
            initial['description'] = self.original_object.description
        return initial

    def get(self, request, *args, **kwargs):
        self.original_object = self.get_original_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.original_object = self.get_original_object()
        return super().post(request, *args, **kwargs)


class CollectionDetailView(views.OwnedObjectDetailView):
    template_name = 'collection_detail.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionUpdateView(ModelFormAndModelFormSetMixin, views.OwnedObjectUpdateView):
    model = models.Collection
    form_class = forms.CollectionModelForm
    formset_model = models.WasteFlyer
    formset_class = forms.WasteFlyerModelFormSet
    formset_form_class = forms.WasteFlyerModelForm
    permission_required = 'soilcom.change_collection'
    template_name = 'collection_form_card.html'

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({
            'parent_object': self.object,
            'queryset': self.formset_model.objects.filter(collections=self.kwargs['pk'])
        })
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'waste_category': self.object.waste_stream.category,
            'allowed_materials': self.object.waste_stream.allowed_materials.all(),
        })
        return initial

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self.get_formset()

        if form.is_valid() and formset.is_valid():
            collection = form.save()
            for form in formset:
                form.instance.owner = request.user
            flyers = formset.save()
            for flyer in flyers:
                if flyer not in collection.flyers.all():
                    collection.flyers.add(flyer)
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class SelectNewlyCreatedObjectModelSelectOptionsView(views.OwnedObjectModelSelectOptionsView):

    def get_selected_object(self):
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


class CollectionModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collection
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collection-list')
    permission_required = 'soilcom.delete_collection'


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
            catchment = Catchment.objects.get(id=catchment_id)
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

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = {'geoJson': serializer.data}
        return JsonResponse(data)


class CollectionCSVAPIView(GenericAPIView):
    queryset = models.Collection.objects.all()
    serializer_class = serializers.WasteCollectionGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = filters.CollectionFilter

    def get(self, request, *args, **kwargs):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="collections.csv"'},
        )
        field_names = ['Catchment', 'NUTS Id', 'Collector', 'Collection System', 'Country', 'Waste Category', 'Allowed Materials',
                       'Connection Rate', 'Connection Rate Year', 'Frequency', 'Comments', 'Sources']
        writer = csv.DictWriter(response, fieldnames=field_names, delimiter='\t')
        writer.writeheader()
        for collection in self.filter_queryset(self.get_queryset()):
            for allowed_material in collection.waste_stream.allowed_materials.all():
                values = {
                    'Allowed Materials': allowed_material,
                    'Waste Category': collection.waste_stream.category,
                    'Connection Rate': collection.connection_rate,
                    'Connection Rate Year': collection.connection_rate_year,
                    'Sources': f'{", ".join([flyer.url for flyer in collection.flyers.all() if type(flyer.url) == str])}'
                }
                if collection.catchment:
                    values['Catchment'] = collection.catchment.name
                    try:
                        values['Country'] = collection.catchment.region.country_code
                    except AttributeError:
                        values['Country'] = ''
                    try:
                        values['NUTS Id'] = collection.catchment.region.nutsregion.nuts_id
                    except:
                        values['NUTS Id'] = ''
                else:
                    values['Catchment'] = ''
                if collection.collector:
                    values['Collector'] = collection.collector.name
                else:
                    values['Collector'] = ''
                if collection.collection_system:
                    values['Collection System'] = collection.collection_system.name
                else:
                    values['Collection System'] = ''
                if collection.frequency:
                    values['Frequency'] = collection.frequency.name
                else:
                    values['Frequency'] = ''
                if collection.description:
                    values['Comments'] = collection.description.replace('\n', '').replace('\r', '')
                else:
                    values['Comments'] = ''
                writer.writerow(values)
        return response


# class CollectionSummaryAPI(ListAPIView):
#     queryset = models.Collection.objects.all()
#     serializer_class = serializers.CollectionModelSerializer
#     filter_backends = (rf_filters.DjangoFilterBackend,)
#     filterset_class = filters.CollectionFilter

class CollectionSummaryAPI(APIView):

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
