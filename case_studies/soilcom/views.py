from dal import autocomplete
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Max, Q
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views.generic import TemplateView

from django_filters.views import FilterMixin, FilterView
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
    template_name = 'simple_detail_card.html'
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
    template_name = 'simple_list_card.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


# class CollectionFilterView(PermissionRequiredMixin, FilterView):
#     template_name = 'collection_filter.html'
#     queryset = models.Collection.objects.filter(catchment__name__icontains='Hamburg')
#     filterset_class = filters.CollectionFilter
#     permission_required = set()


class CollectionFilterView(views.OwnedObjectListView):
    template_name = 'collection_filter.html'
    model = models.Collection
    queryset = models.Collection.objects.all()
    # filterset_class = filters.CollectionFilter
    permission_required = set()

    def get_queryset(self):
        queryset = super().get_queryset()
        filter = filters.CollectionFilter(self.request.GET, queryset)
        return filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        filter = filters.CollectionFilter(self.request.GET, queryset)
        context['filter'] = filter
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
    success_url = reverse_lazy('WasteCollection')
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
            self.object.flyers.set(list(flyers))
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = self.get_context_data(form=form, formset=formset)
            return self.render_to_response(context)


class CollectionCopyView(CollectionCreateView):
    model = models.Collection

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({
            'parent_object': self.object,
            'queryset': self.formset_model.objects.filter(collections=self.kwargs['pk'])
        })
        return super().get_formset_kwargs(**kwargs)

    def get_initial(self):
        collection = self.get_object()
        initial = {}
        if collection.catchment:
            initial['catchment'] = collection.catchment
        if collection.collector:
            initial['collector'] = collection.collector
        if collection.collection_system:
            initial['collection_system'] = collection.collection_system
        if collection.waste_stream:
            if collection.waste_stream.category:
                initial['waste_category'] = collection.waste_stream.category
            if collection.waste_stream.allowed_materials.exists():
                initial['allowed_materials'] = collection.waste_stream.allowed_materials.all()
        if collection.connection_rate:
            initial['connection_rate'] = collection.connection_rate
        if collection.connection_rate_year:
            initial['connection_rate_year'] = collection.connection_rate_year
        if collection.frequency:
            initial['frequency'] = collection.frequency
        if collection.description:
            initial['description'] = collection.description
        return initial


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
    feature_url = reverse_lazy('data.collections')
    feature_summary_url = reverse_lazy('data.collection-summary')
    form_class = forms.CollectionFilterForm
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
            'collection_system': self.request.GET.getlist('collection_system[]'),
            'waste_category': self.request.GET.getlist('waste_category[]'),
            'countries': self.request.GET.getlist('countries[]'),
            'allowed_materials': self.request.GET.getlist('allowed_materials[]')
        })
        return initial

    def get_object(self, **kwargs):
        self.kwargs.update({'pk': GeoDataset.objects.get(model_name='WasteCollection').pk})
        return super().get_object(**kwargs)


# ----------- API ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteCollectionAPIView(APIView):

    @staticmethod
    def get(request):
        if request.query_params:
            qs = models.Collection.objects.all()
        else:
            qs = models.Collection.objects.none()

        countries = request.query_params.getlist('countries[]')
        if countries:
            qs = qs.filter(
                Q(catchment__region__nutsregion__cntr_code__in=countries) |
                Q(catchment__region__lauregion__cntr_code__in=countries))

        collection_system = request.query_params.getlist('collection_system[]')
        if collection_system:
            qs = qs.filter(collection_system_id__in=collection_system)

        waste_category = request.query_params.getlist('waste_category[]')
        if waste_category:
            qs = qs.filter(waste_stream__category_id__in=waste_category)

        allowed_materials_ids = request.query_params.getlist('allowed_materials[]')
        if allowed_materials_ids:
            for material_id in allowed_materials_ids:
                qs = qs.filter(waste_stream__allowed_materials__id=material_id)

        last_editor = request.query_params.getlist('last_editor[]')
        if last_editor:
            qs = qs.filter(lastmodified_by__in=last_editor)

        serializer = serializers.WasteCollectionGeometrySerializer(qs, many=True)
        data = {'geoJson': serializer.data}
        return JsonResponse(data)


class WasteCollectionSummaryAPIView(APIView):

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


class WasteCollectionPopupDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_collection_popup.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'

    def get_object(self, **kwargs):
        return self.model.objects.get(id=self.request.GET.get('pk'))
