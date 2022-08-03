from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, TemplateView
from django.views.generic.edit import FormMixin

from dal import autocomplete
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.views import APIView, Response

from brit.views import (
    OwnedObjectListView,
    OwnedObjectCreateView,
    OwnedObjectModalCreateView,
    OwnedObjectDetailView,
    OwnedObjectModalDetailView,
    OwnedObjectUpdateView,
    OwnedObjectModalUpdateView,
    OwnedObjectDeleteView,
    OwnedObjectModelSelectOptionsView
)
from maps.serializers import (
    RegionSerializer, CatchmentSerializer, NutsRegionGeometrySerializer,
    NutsRegionCatchmentOptionSerializer, NutsRegionSummarySerializer, LauRegionOptionSerializer,
    LauRegionSummarySerializer,
    NutsRegionOptionSerializer)
from .forms import (
    AttributeModelForm,
    AttributeModalModelForm,
    CatchmentModelForm,
    CatchmentQueryForm,
    NutsRegionQueryForm,
    RegionAttributeValueModelForm,
    RegionAttributeValueModalModelForm
)
from .models import (
    Attribute,
    RegionAttributeValue,
    Catchment,
    GeoDataset,
    Region,
    NutsRegion,
    LauRegion
)


class MapsListView(ListView):
    template_name = 'maps_list.html'

    def get_queryset(self):
        user_groups = self.request.user.groups.all()
        return GeoDataset.objects.filter(Q(visible_to_groups__in=user_groups) | Q(publish=True)).distinct()


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentBrowseView(FormMixin, TemplateView):
    model = Catchment
    form_class = CatchmentQueryForm
    template_name = 'catchment_list.html'
    region_url = reverse_lazy('ajax_region_geometries')
    feature_url = reverse_lazy('data.catchment-options')
    filter_class = None
    load_features = False
    adjust_bounds_to_features = False
    load_region = True
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
            'nuts_form': NutsRegionQueryForm,
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
        return 3


class CatchmentCreateView(LoginRequiredMixin, CreateView):
    template_name = 'catchment_create.html'
    form_class = CatchmentModelForm
    success_url = reverse_lazy('catchment_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CatchmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Catchment
    form_class = CatchmentModelForm

    def get_success_url(self):
        return reverse('catchment_list')

    def test_func(self):
        catchment = Catchment.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == catchment.owner


class CatchmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Catchment
    success_url = reverse_lazy('catchment_list')

    def test_func(self):
        catchment = Catchment.objects.get(id=self.kwargs.get('pk'))
        return catchment.owner == self.request.user


# ----------- Catchment utilities---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Catchment.objects.all().order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- Geodataset -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoDataSetMixin:
    feature_url = None
    feature_summary_url = None
    region_url = reverse_lazy('ajax_region_geometries')
    load_region = True
    region_id = None
    load_catchment = False
    catchment_id = None
    load_features = False
    adjust_bounds_to_features = False
    marker_style = None
    map_title = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_title': self.get_map_title(),
            'map_config': {
                'region_url': self.get_region_url(),
                'feature_url': self.get_feature_url(),
                'feature_summary_url': self.get_feature_summary_url(),
                'load_features': self.get_load_features(),
                'adjust_bounds_to_features': self.adjust_bounds_to_features,
                'region_id': self.get_region_id(),
                'load_region': self.load_region,
                'catchment_id': self.get_catchment_id(),
                'load_catchment': self.load_catchment,
                'markerStyle': self.get_marker_style()
            }
        })
        return context

    def get_map_title(self):
        return self.map_title

    def get_feature_url(self):
        return self.feature_url

    def get_feature_summary_url(self):
        return self.feature_summary_url

    def get_region_url(self):
        return self.region_url

    def get_region_id(self):
        return self.region_id

    def get_catchment_id(self):
        return self.catchment_id

    def get_load_features(self):
        if self.request.GET.get('load_features'):
            return self.request.GET.get('load_features') == 'true'
        else:
            return self.load_features

    def get_marker_style(self):
        return self.marker_style


class GeoDataSetFormMixin(FormMixin):
    filterset_class = None
    form_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['map_config'].update({
            'form_fields': self.get_form_fields(),
        })
        context.update({
            'form': self.get_form(),
        })
        return context

    def get_form(self, form_class=None):
        if self.form_class is not None:
            return self.form_class(**self.get_form_kwargs())
        if self.filterset_class is not None:
            return self.filterset_class(self.request.GET).form

    def get_filter_fields(self):
        return {key: type(value.field.widget).__name__ for key, value in self.filterset_class.base_filters.items()}

    def get_form_fields(self):
        if self.form_class is None and self.filterset_class is not None:
            return self.get_filter_fields()
        return {key: type(value.widget).__name__ for key, value in self.form_class.base_fields.items()}


class GeoDatasetDetailView(GeoDataSetFormMixin, GeoDataSetMixin, DetailView):
    model = GeoDataset
    template_name = 'maps_base.html'

    def get_map_title(self):
        return self.object.name

    def get_region_id(self):
        return self.object.region.id


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentGeometryAPI(APIView):

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if 'catchment' in request.query_params:
            catchment_id = request.query_params.get('catchment')
            catchment = Catchment.objects.get(id=catchment_id)
            region_id = catchment.region_id
            regions = Region.objects.filter(id=region_id)
            serializer = RegionSerializer(regions, many=True)
            data = {
                'geoJson': serializer.data,
                'info': {
                    'name': {
                        'label': 'Name',
                        'value': catchment.name,
                    },
                    'description': {
                        'label': 'Description',
                        'value': catchment.description
                    },
                    'parent_region': {
                        'label': 'Parent region',
                        'value': catchment.parent_region.name
                    }
                }
            }
            return JsonResponse(data)

        return JsonResponse({})


class CatchmentOptionGeometryAPI(APIView):

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        qs = Catchment.objects.all()

        if 'parent_id' in request.query_params:
            parent_id = request.query_params['parent_id']
            parent_catchment = Catchment.objects.get(id=parent_id)
            parent_region = parent_catchment.region
            qs = parent_region.child_catchments.all()
            serializer = CatchmentSerializer(qs, many=True)
            return JsonResponse({'geoJson': serializer.data})


class RegionGeometryAPI(APIView):
    """
    Takes the id of a region and returns its geometry as GeoJSON.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if 'pk' in request.query_params:
            region_id = request.query_params.get('pk')
            regions = Region.objects.filter(id=region_id)
            serializer = RegionSerializer(regions, many=True)
            return JsonResponse({'geoJson': serializer.data})

        return JsonResponse({})


# ----------- NutsRegions ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class NutsRegionSummaryAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        obj = NutsRegion.objects.filter(id=request.query_params.get('pk'))
        serializer = NutsRegionSummarySerializer(
            obj,
            many=True,
            field_labels_as_keys=True,
            context={'request': request})
        return Response({'summaries': serializer.data})


class CatchmentRegionGeometryAPI(APIView):
    """
    Similar to RegionGeometryAPI. Instead of taking the id of the requested region, this takes a catchment id as input
    and returns the geometry of the associated Region.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if 'pk' in request.query_params:
            catchment = Catchment.objects.get(pk=request.query_params.get('pk'))
            regions = Region.objects.filter(catchment=catchment)
            serializer = RegionSerializer(regions, many=True)
            return JsonResponse({'geoJson': serializer.data})

        return JsonResponse({})


class CatchmentRegionSummaryAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if 'pk' in request.query_params:
            catchment = Catchment.objects.get(pk=request.query_params.get('pk'))
            try:
                region = catchment.region.nutsregion
                serializer = NutsRegionSummarySerializer(
                    region,
                    field_labels_as_keys=True,
                    context={'request': request})
                return Response({'summaries': [serializer.data]})
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass

            try:
                region = catchment.region.lauregion
                serializer = LauRegionSummarySerializer(
                    region,
                    field_labels_as_keys=True,
                    context={'request': request})
                return Response({'summaries': [serializer.data]})
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass

        return Response({})


# ----------- NUTS Map -------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NutsRegionMapView(GeoDatasetDetailView):
    template_name = 'nuts_region_map.html'
    feature_url = reverse_lazy('data.nutsregion')
    feature_summary_url = reverse_lazy('data.nutsregion-summary')
    region_url = reverse_lazy('data.nutsregion')
    form_class = NutsRegionQueryForm
    load_features = False
    adjust_bounds_to_features = True
    load_region = False
    marker_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'stroke': False
    }

    def get_object(self, **kwargs):
        self.kwargs.update({'pk': GeoDataset.objects.get(model_name='NutsRegion').pk})
        return super().get_object(**kwargs)


class NutsRegionAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        qs = NutsRegion.objects.all()

        if 'pk' in request.query_params:
            qs = qs.filter(pk=request.query_params['pk'])
        if 'levl_code' in request.query_params:
            qs = qs.filter(levl_code=request.query_params['levl_code'])
        if 'cntr_code[]' in request.query_params:
            qs = qs.filter(cntr_code__in=request.query_params.getlist('cntr_code[]'))
        if 'parent_id' in request.query_params:
            qs = qs.filter(parent_id=request.query_params['parent_id'])

        serializer = NutsRegionGeometrySerializer(qs, many=True)
        return JsonResponse({'geoJson': serializer.data})


class NutsRegionPedigreeAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):

        if 'id' not in request.query_params:
            raise ParseError('Query parameter "id" missing. Must provide valid id of NUTS region.')

        if 'direction' not in request.query_params or request.query_params['direction'] not in ('children', 'parents'):
            raise ParseError('Missing or wrong query parameter "direction". Options: "parents", "children"')

        try:
            instance = NutsRegion.objects.get(id=request.query_params['id'])
        except AttributeError:
            raise NotFound('A NUTS region with the provided id does not exist.')
        except NutsRegion.DoesNotExist:
            raise NotFound('A NUTS region with the provided id does not exist.')

        data = {}

        if request.query_params['direction'] == 'children':
            for lvl in range(instance.levl_code + 1, 4):
                qs = NutsRegion.objects.filter(levl_code=lvl, nuts_id__startswith=instance.nuts_id)
                serializer = NutsRegionOptionSerializer(qs, many=True)
                data[f'id_level_{lvl}'] = serializer.data

        if request.query_params['direction'] == 'parents':
            for lvl in range(instance.levl_code - 1, -1, -1):
                instance = instance.parent
                serializer = NutsRegionOptionSerializer(instance)
                data[f'id_level_{lvl}'] = serializer.data

        return Response(data)


class LauRegionOptionsAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        data = {}
        qs = LauRegion.objects.all()
        serializer = LauRegionOptionSerializer(qs, many=True)
        data['id_lau'] = serializer.data

        return JsonResponse(data)


class NutsAndLauCatchmentPedigreeAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):

        if 'id' not in request.query_params:
            raise ParseError('Query parameter "id" missing. Must provide valid catchment id.')

        if 'direction' not in request.query_params or request.query_params['direction'] not in ('children', 'parents'):
            raise ParseError('Missing or wrong query parameter "direction". Options: "parents", "children"')

        try:
            catchment = Catchment.objects.get(id=request.query_params['id'])
            instance = catchment.region.nutsregion
        except AttributeError:
            raise NotFound('A NUTS region with the provided id does not exist.')
        except Catchment.DoesNotExist:
            raise NotFound('A NUTS region with the provided id does not exist.')

        data = {}

        if request.query_params['direction'] == 'children':
            for lvl in range(instance.levl_code + 1, 4):
                qs = NutsRegion.objects.filter(levl_code=lvl, nuts_id__startswith=instance.nuts_id)
                serializer = NutsRegionCatchmentOptionSerializer(qs, many=True)
                data[f'id_level_{lvl}'] = serializer.data
            data['id_level_4'] = []
            if instance.levl_code == 3:
                qs = LauRegion.objects.filter(nuts_parent=instance)
                serializer = LauRegionOptionSerializer(qs, many=True)
                data[f'id_level_4'] = serializer.data

        if request.query_params['direction'] == 'parents':
            for lvl in range(instance.levl_code - 1, -1, -1):
                instance = instance.parent
                serializer = NutsRegionCatchmentOptionSerializer(instance)
                data[f'id_level_{lvl}'] = serializer.data

        return Response(data)


# ----------- Attribute CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class AttributeListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Attribute
    permission_required = set()


class AttributeCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = AttributeModelForm
    success_url = reverse_lazy('attribute-list')
    permission_required = 'maps.add_attribute'


class AttributeModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = AttributeModalModelForm
    success_url = reverse_lazy('attribute-list')
    permission_required = 'maps.add_attribute'


class AttributeDetailView(OwnedObjectDetailView):
    template_name = 'attribute_detail.html'
    model = Attribute
    permission_required = set()


class AttributeModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Attribute
    permission_required = set()


class AttributeUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Attribute
    form_class = AttributeModelForm
    permission_required = 'maps.change_attribute'


class AttributeModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Attribute
    form_class = AttributeModalModelForm
    permission_required = 'maps.change_attribute'


class AttributeModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Attribute
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('attribute-list')
    permission_required = 'maps.delete_attribute'


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class RegionAttributeValueListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = RegionAttributeValue
    permission_required = set()


class RegionAttributeValueCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = RegionAttributeValueModelForm
    success_url = reverse_lazy('regionattributevalue-list')
    permission_required = 'maps.add_regionattributevalue'


class RegionAttributeValueModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = RegionAttributeValueModalModelForm
    success_url = reverse_lazy('regionattributevalue-list')
    permission_required = 'maps.add_regionattributevalue'


class RegionAttributeValueDetailView(OwnedObjectDetailView):
    template_name = 'regionattributevalue_detail.html'
    model = RegionAttributeValue
    permission_required = set()


class RegionAttributeValueModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = RegionAttributeValue
    permission_required = set()


class RegionAttributeValueUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = RegionAttributeValue
    form_class = RegionAttributeValueModelForm
    permission_required = 'maps.change_regionattributevalue'


class RegionAttributeValueModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = RegionAttributeValue
    form_class = RegionAttributeValueModalModelForm
    permission_required = 'maps.change_regionattributevalue'


class RegionAttributeValueModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = RegionAttributeValue
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('regionattributevalue-list')
    permission_required = 'maps.delete_regionattributevalue'


class RegionChildCatchmentOptions(OwnedObjectModelSelectOptionsView):
    model = Catchment
