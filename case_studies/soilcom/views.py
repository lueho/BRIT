from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Max, Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin
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
from maps.forms import NutsRegionQueryForm
from maps.models import Catchment, GeoDataset, NutsRegion
from maps.views import GeoDatasetDetailView
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
    create_new_object_url = reverse_lazy('wasteflyer-create')


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


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionCreateView(views.OwnedObjectCreateView):
    template_name = 'collection_form_card.html'
    form_class = forms.CollectionModelForm
    success_url = reverse_lazy('WasteCollection')
    permission_required = 'soilcom.add_collection'

    def get_initial(self):
        initial = super().get_initial()
        if 'region_id' in self.request.GET:
            region_id = self.request.GET.get('region_id')
            catchment = NutsRegion.objects.get(id=region_id).region_ptr.catchment_set.first()
            initial['catchment'] = catchment
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        name = f'{data["catchment"]} {data["waste_category"]} {data["collection_system"]}'

class CollectionCopyView(CollectionCreateView):
    model = models.Collection

    def get_initial(self):
        collection = self.get_object()
        initial = {
            'catchment': collection.catchment,
            'collector': collection.collector,
            'collection_system': collection.collection_system,
            'waste_category': collection.waste_stream.category,
            'allowed_materials': collection.waste_stream.allowed_materials.all(),
            'flyer_url': collection.flyer.url,
            'description': collection.description
        }
        return initial


class CollectionModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionModalModelForm
    success_url = reverse_lazy('collection-list')
    permission_required = 'soilcom.add_collection'


class CollectionDetailView(views.OwnedObjectDetailView):
    template_name = 'collection_detail.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'


class CollectionUpdateView(views.OwnedObjectUpdateView):
    template_name = 'collection_form_card.html'
    model = models.Collection
    form_class = forms.CollectionModelForm
    permission_required = 'soilcom.change_collection'
    success_url = reverse_lazy('WasteCollection')

    def get_initial(self):
        initial = super().get_initial()
        initial['catchment'] = self.object.catchment
        initial['waste_category'] = self.object.waste_stream.category
        initial['allowed_materials'] = self.object.waste_stream.allowed_materials.all()
        initial['flyer_url'] = self.object.flyer.url if self.object.flyer else ''
        return initial

    def form_valid(self, form):
        waste_stream = self.object.waste_stream
        allowed_materials = form.cleaned_data['allowed_materials'].all()
        for material in waste_stream.allowed_materials.all():
            if material not in allowed_materials:
                waste_stream.allowed_materials.remove(material)
        for material in allowed_materials:
            if material not in waste_stream.allowed_materials.all():
                waste_stream.allowed_materials.add(material)
        waste_stream.save()
        if form.cleaned_data['flyer_url']:
            region_id = None
            try:
                region_id = form.cleaned_data["catchment"].region.nutsregion.nuts_id
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass
            try:
                region_id = form.cleaned_data["catchment"].region.lauregion.lau_id
            except Region.lauregion.RelatedObjectDoesNotExist:
                pass

            flyer, created = models.WasteFlyer.objects.get_or_create(
                type='waste_flyer',
                url=form.cleaned_data['flyer_url'],
                defaults={
                    'owner': self.request.user,
                    'title': f'Waste flyer {form.cleaned_data["catchment"]}',
                    'abbreviation': f'WasteFlyer{region_id}',
                }
            )
            form.instance.flyer = flyer
        return super().form_valid(form)


class CollectorOptions(CollectorListView):
    template_name = 'selection_options.html'
    object_list = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        created_at = models.Collector.objects.aggregate(max_created_at=Max('created_at'))['max_created_at']
        collector = models.Collector.objects.get(created_at=created_at)
        context.update({'selected': collector.pk})
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return JsonResponse({
            'options': render_to_string(
                self.template_name,
                context=self.get_context_data(),
                request=self.request
            )
        })


class CollectionModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.Collection
    form_class = forms.CollectionModalModelForm
    permission_required = 'soilcom.change_collection'


class CollectionModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collection
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collection-list')
    permission_required = 'soilcom.delete_collection'


# ----------- Maps -----------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentSelectView(FormMixin, TemplateView):
    model = Catchment
    form_class = NutsRegionQueryForm
    template_name = 'waste_collection_catchment_list.html'
    region_url = reverse_lazy('ajax_region_geometries')
    feature_url = reverse_lazy('data.catchment-options')
    filter_class = None
    load_features = False
    queryset = NutsRegion.objects.filter(levl_code=0)
    adjust_bounds_to_features = False
    load_region = False
    marker_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'stroke': False
    }

    def get_initial(self):
        initial = {}
        region_id = self.request.GET.get('region')
        catchment_id = self.request.GET.get('catchment')
        if catchment_id:
            catchment = Catchment.objects.get(id=catchment_id)
            initial['parent_region'] = catchment.parent_region.id
            initial['catchment'] = catchment.id
        elif region_id:
            initial['region'] = region_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_header': 'Catchments',
            'form': self.get_form(),
            'map_config': {
                'form_fields': self.get_form_fields(),
                'region_url': self.region_url,
                'feature_url': self.feature_url,
                'load_features': self.load_features,
                'adjust_bounds_to_features': self.adjust_bounds_to_features,
                'region_id': self.get_region_id(),
                'load_region': self.load_region,
                'markerStyle': self.marker_style
            }
        })
        return context

    def get_form_fields(self):
        return {key: type(value.widget).__name__ for key, value in self.form_class.base_fields.items()}

    def get_region_id(self):
        return 10


class WasteCollectionMapView(GeoDatasetDetailView):
    template_name = 'waste_collection_map.html'
    feature_url = reverse_lazy('data.collections')
    feature_popup_url = reverse_lazy('data.collection-summary')
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
        collection_system = self.request.GET.getlist('collection_system[]')
        waste_category = self.request.GET.getlist('waste_category[]')
        countries = self.request.GET.getlist('countries[]')
        allowed_materials = self.request.GET.getlist('allowed_materials[]')
        initial.update({
            'collection_system': collection_system,
            'waste_category': waste_category,
            'countries': countries,
            'allowed_materials': allowed_materials
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
        obj = models.Collection.objects.get(id=request.query_params.get('collection_id'))
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
        return self.model.objects.get(id=self.request.GET.get('collection_id'))
