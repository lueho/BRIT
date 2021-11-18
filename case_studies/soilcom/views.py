from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from rest_framework.views import APIView

from bibliography.views import (SourceListView,
                                SourceCreateView,
                                SourceModalCreateView,
                                SourceDetailView,
                                SourceModalDetailView,
                                SourceUpdateView,
                                SourceModalUpdateView,
                                SourceModalDeleteView)

from brit import views

from maps.views import GeoDatasetDetailView
from materials.models import MaterialGroup

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
    create_new_object_url = reverse_lazy('collector_create')


class CollectorCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectorModelForm
    success_url = reverse_lazy('collector_list')
    permission_required = 'soilcom.add_collector'


class CollectorModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectorModalModelForm
    success_url = reverse_lazy('collector_list')
    permission_required = 'soilcom.add_collector'


class CollectorDetailView(views.OwnedObjectDetailView):
    template_name = 'collector_detail.html'
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
    success_url = reverse_lazy('collector_list')
    permission_required = 'soilcom.delete_collector'


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionSystemListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.CollectionSystem
    permission_required = 'soilcom.view_collectionsystem'
    create_new_object_url = reverse_lazy('collection_system_create')


class CollectionSystemCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionSystemModelForm
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionSystemModalModelForm
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'soilcom.add_collectionsystem'


class CollectionSystemDetailView(views.OwnedObjectDetailView):
    template_name = 'collection_system_detail.html'
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
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'soilcom.delete_collectionsystem'


# ----------- Waste Stream Category CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteCategoryListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteCategory
    permission_required = 'soilcom.view_wastecategory'
    create_new_object_url = reverse_lazy('waste_category_create')


class WasteCategoryCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteCategoryModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteCategoryModalModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'soilcom.add_wastecategory'


class WasteCategoryDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_category_detail.html'
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
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'soilcom.delete_wastecategory'


# ----------- Waste Component CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteComponentListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteComponent
    permission_required = 'soilcom.view_wastecomponent'
    create_new_object_url = reverse_lazy('waste_component_create')


class WasteComponentCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteComponentModelForm
    success_url = reverse_lazy('waste_component_list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteComponentModalModelForm
    success_url = reverse_lazy('waste_component_list')
    permission_required = 'soilcom.add_wastecomponent'


class WasteComponentDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_component_detail.html'
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
    success_url = reverse_lazy('waste_component_list')
    permission_required = 'soilcom.delete_wastecomponent'


# ----------- Waste Stream CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteStreamListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteStream
    permission_required = 'soilcom.view_wastestream'
    create_new_object_url = reverse_lazy('waste_stream_create')


class WasteStreamCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteStreamModelForm
    success_url = reverse_lazy('waste_stream_list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteStreamModalModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'soilcom.add_wastestream'


class WasteStreamDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_stream_detail.html'
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
    success_url = reverse_lazy('waste_stream_list')
    permission_required = 'soilcom.delete_wastestream'


# ----------- Waste Collection Flyer CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteFlyerListView(SourceListView):
    template_name = 'waste_flyers_list.html'
    model = models.WasteFlyer
    permission_required = 'soilcom.view_wasteflyer'
    create_new_object_url = reverse_lazy('waste_flyer_create')


class WasteFlyerCreateView(SourceCreateView):
    form_class = forms.WasteFlyerModelForm
    success_url = reverse_lazy('waste_flyer_list')
    permission_required = 'soilcom.add_wasteflyer'

    def form_valid(self, form):
        form.instance.type = 'waste_flyer'
        return super().form_valid(form)


class WasteFlyerModalCreateView(SourceModalCreateView):
    form_class = forms.WasteFlyerModalModelForm
    success_url = reverse_lazy('waste_flyer_list')
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
    success_url = reverse_lazy('waste_flyer_list')
    permission_required = 'soilcom.delete_wasteflyer'


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'
    create_new_object_url = reverse_lazy('waste_collection_create')


class CollectionCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionModelForm
    success_url = reverse_lazy('waste_collection_list')
    permission_required = 'soilcom.add_collection'


class CollectionModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionModalModelForm
    success_url = reverse_lazy('waste_collection_list')
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
    template_name = 'simple_form_card.html'
    model = models.Collection
    form_class = forms.CollectionModelForm
    permission_required = 'soilcom.change_collection'


class CollectionModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.Collection
    form_class = forms.CollectionModalModelForm
    permission_required = 'soilcom.change_collection'


class CollectionModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collection
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('waste_collection_list')
    permission_required = 'soilcom.delete_collection'


# ----------- Maps -----------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteCollectionMapView(GeoDatasetDetailView):
    feature_url = reverse_lazy('data.waste_collections')
    feature_popup_url = reverse_lazy('data.waste_collection_summary')
    form_class = forms.CollectionFilterForm
    load_features = True
    adjust_bounds_to_features = True
    load_region = False
    marker_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'stroke': False
    }


# ----------- API ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteCollectionAPIView(APIView):

    @staticmethod
    def get(request):
        qs = models.Collection.objects.all()
        serializer = serializers.WasteCollectionGeometrySerializer(qs, many=True)
        data = {'geoJson': serializer.data}
        return JsonResponse(data)


class WasteCollectionSummaryAPIView(APIView):

    @staticmethod
    def get(request):
        obj = models.Collection.objects.get(id=request.query_params.get('collection_id'))
        serializer = serializers.WasteCollectionSerializer(obj, context={'request': request})
        return JsonResponse(serializer.verbose_data)


class WasteCollectionPopupDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_collection_popup.html'
    model = models.Collection
    permission_required = 'soilcom.view_collection'

    def get_object(self, **kwargs):
        return self.model.objects.get(id=self.request.GET.get('collection_id'))
