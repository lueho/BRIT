from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.gis.geos import MultiPolygon
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q, Subquery
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import DetailView, TemplateView
from django.views.generic.edit import FormMixin
from django_filters.views import FilterView
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.views import APIView, Response

from maps.serializers import (CatchmentSerializer, LauRegionOptionSerializer, LauRegionSummarySerializer,
                              NutsRegionCatchmentOptionSerializer, NutsRegionGeometrySerializer,
                              NutsRegionOptionSerializer, NutsRegionSummarySerializer, RegionGeoFeatureModelSerializer)
from utils.forms import DynamicTableInlineFormSetHelper
from utils.views import (BRITFilterView, OwnedObjectCreateView, OwnedObjectDetailView, OwnedObjectListView,
                         OwnedObjectModalCreateView, OwnedObjectModalDeleteView, OwnedObjectModalDetailView,
                         OwnedObjectModalUpdateView, OwnedObjectModelSelectOptionsView, PublishedObjectFilterView,
                         OwnedObjectUpdateView, RestrictedOwnedObjectDetailView, UserOwnedObjectFilterView)
from .filters import CatchmentFilter, RegionFilterSet, NutsRegionFilterSet, GeoDataSetFilterSet
from .forms import (AttributeModalModelForm, AttributeModelForm, CatchmentCreateDrawCustomForm,
                    CatchmentCreateMergeLauForm, CatchmentModelForm,
                    RegionModelForm, RegionAttributeValueModalModelForm,
                    RegionAttributeValueModelForm, RegionMergeForm, RegionMergeFormSet, LocationModelForm)
from .models import (Attribute, Catchment, GeoDataset, GeoPolygon, LauRegion, Location, NutsRegion, Region,
                     RegionAttributeValue)


class MapMixin:
    """
    Provides functionality for the integration of maps with leaflet.
    """
    map_title = None
    load_region = True
    region_id = None
    region_url = None
    region_layer_style = None
    load_catchment = True
    catchment_url = None
    catchment_id = None
    catchment_layer_style = None
    load_features = True
    feature_url = None
    apply_filter_to_features = False
    feature_layer_style = None
    adjust_bounds_to_features = True
    feature_summary_url = None
    api_basename = None
    feature_details_url = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_title': self.get_map_title(),
            'map_config': {
                'loadRegion': self.get_load_region(),
                'regionId': self.get_region_id(),
                'regionUrl': self.get_region_url(),
                'regionLayerStyle': self.get_region_layer_style(),
                'loadCatchment': self.get_load_catchment(),
                'catchmentId': self.get_catchment_id(),
                'catchmentUrl': self.get_catchment_url(),
                'catchmentLayerStyle': self.get_catchment_layer_style(),
                'loadFeatures': self.get_load_features(),
                'featureUrl': self.get_apply_filter_to_features(),
                'applyFilterToFeatures': self.get_use_filter(),
                'featureLayerStyle': self.get_feature_layer_style(),
                'adjustBoundsToFeatures': self.get_adjust_bounds_to_features(),
                'featureSummaryUrl': self.get_feature_summary_url(),
                'featureDetailsUrl': self.get_feature_details_url(),
            }
        })
        return context

    def get_map_title(self):
        return self.map_title

    def get_load_region(self):
        if self.request.GET.get('load_region'):
            return self.request.GET.get('load_region') == 'true'
        else:
            return self.load_region

    def get_region_id(self):
        return self.region_id

    def get_region_url(self):
        return self.region_url

    def get_region_layer_style(self):
        if not self.region_layer_style:
            self.region_layer_style = {
                'color': '#A1221C',
                'fillOpacity': 0.0
            }
        return self.region_layer_style

    def get_load_catchment(self):
        if self.request.GET.get('load_catchment'):
            return self.request.GET.get('load_catchment') == 'true'
        else:
            return self.load_catchment

    def get_catchment_id(self):
        return self.catchment_id

    def get_catchment_url(self):
        return self.catchment_url

    def get_catchment_layer_style(self):
        if not self.catchment_layer_style:
            self.catchment_layer_style = {
                'color': '#A1221C',
                'fillOpacity': 0.0
            }
        return self.catchment_layer_style

    def get_load_features(self):
        if self.request.GET.get('load_features'):
            return self.request.GET.get('load_features') == 'true'
        else:
            return self.load_features

    def get_apply_filter_to_features(self):
        return self.feature_url

    def get_use_filter(self):
        return self.apply_filter_to_features

    def get_feature_layer_style(self):
        if not self.feature_layer_style:
            self.feature_layer_style = {
                'color': '#04555E',
            }
        return self.feature_layer_style

    def get_adjust_bounds_to_features(self):
        return self.adjust_bounds_to_features

    def get_feature_summary_url(self):
        return self.feature_summary_url

    def get_api_basename(self):
        return self.api_basename

    def get_feature_details_url(self):
        if not self.feature_details_url and self.api_basename:
            self.feature_details_url = reverse(f'{self.api_basename}-detail', kwargs={'pk': 0})[:-2]
        return self.feature_details_url


class MapsDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'maps_dashboard.html'
    permission_required = set()


# ----------- Geodataset -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoDataSetMixin(MapMixin):
    region_url = reverse_lazy('data.region-geometries')
    catchment_url = reverse_lazy('data.catchment-geometries')


class PublishedGeoDatasetFilterView(PublishedObjectFilterView):
    model = GeoDataset
    filterset_class = GeoDataSetFilterSet
    template_name = 'maps_list.html'


class GeoDataSetFormMixin(FormMixin):
    filterset_class = None
    form_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form': self.get_form(),
        })
        return context

    def get_form(self, form_class=None):
        if self.form_class is not None:
            return self.form_class(**self.get_form_kwargs())
        if self.filterset_class is not None:
            return self.filterset_class(self.request.GET).form


class GeoDataSetDetailView(GeoDataSetMixin, FilterView):
    model_name = None
    filterset_class = None
    template_name = 'filtered_map.html'

    def get_object(self):
        try:
            return GeoDataset.objects.get(model_name=self.model_name)
        except GeoDataset.DoesNotExist:
            raise ImproperlyConfigured(f'No GeoDataset with model_name {self.model_name} found.')

    def get_region_id(self):
        return self.get_object().region.id


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LocationListView(OwnedObjectListView):
    model = Location
    permission_required = set()


class LocationCreateView(OwnedObjectCreateView):
    model = Location
    form_class = LocationModelForm
    permission_required = 'maps.add_location'


class LocationDetailView(MapMixin, OwnedObjectDetailView):
    model = Location
    feature_url = reverse_lazy('api-location-geojson')
    load_region = False
    load_catchment = False
    permission_required = set()


class LocationUpdateView(OwnedObjectUpdateView):
    model = Location
    form_class = LocationModelForm
    permission_required = 'maps.change_location'


class LocationModalDeleteView(OwnedObjectModalDeleteView):
    model = Location
    success_url = reverse_lazy('location-list')
    success_message = 'deletion successful'
    permission_required = 'maps.delete_location'


# ----------- Region CRUD-----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionListView(BRITFilterView):
    model = Region
    filterset_class = RegionFilterSet
    ordering = 'name'


class RegionMapView(LoginRequiredMixin, GeoDataSetMixin, FilterView):
    template_name = 'region_map.html'
    filterset_class = RegionFilterSet
    map_title = 'Regions'
    feature_url = reverse_lazy('api-region-geojson')
    feature_summary_url = reverse_lazy('api-region-list')
    apply_filter_to_features = True
    load_region = False
    load_catchment = False
    load_features = False


class RegionDetailView(MapMixin, DetailView):
    model = Region
    feature_url = reverse_lazy('api-region-geojson')
    load_region = False
    load_catchment = False
    permission_required = set()


class RegionCreateView(OwnedObjectCreateView):
    model = Region
    form_class = RegionModelForm
    permission_required = 'maps.add_region'


class RegionUpdateView(OwnedObjectUpdateView):
    model = Region
    form_class = RegionModelForm
    permission_required = 'maps.change_region'


class RegionModalDeleteView(OwnedObjectModalDeleteView):
    model = Region
    success_url = reverse_lazy('region-list')
    success_message = 'deletion successful'
    permission_required = 'maps.delete_region'


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedCatchmentListView(PublishedObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilter
    ordering = 'name'


class UserOwnedCatchmentListView(UserOwnedObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilter
    ordering = 'name'


class CatchmentDetailView(MapMixin, RestrictedOwnedObjectDetailView):
    model = Catchment
    catchment_url = reverse_lazy('data.catchment-geometries')
    feature_url = reverse_lazy('data.catchment-geometries')
    load_region = False
    load_catchment = False
    permission_required = set()


class CatchmentCreateView(TemplateView):
    template_name = 'catchment_create_method_select.html'


class CatchmentCreateSelectRegionView(LoginRequiredMixin, OwnedObjectCreateView):
    template_name = 'maps/catchment_form.html'
    form_class = CatchmentModelForm
    permission_required = set()


class CatchmentCreateDrawCustomView(LoginRequiredMixin, OwnedObjectCreateView):
    template_name = 'catchment_draw_form.html'
    form_class = CatchmentCreateDrawCustomForm
    permission_required = set()


class CatchmentCreateMergeLauView(LoginRequiredMixin, OwnedObjectCreateView):
    template_name = 'catchment_merge_formset.html'
    form = None
    form_class = CatchmentCreateMergeLauForm
    formset = None
    formset_model = Region
    formset_class = RegionMergeFormSet
    formset_form_class = RegionMergeForm
    formset_helper_class = DynamicTableInlineFormSetHelper
    formset_factory_kwargs = {'extra': 2}
    relation_field_name = 'seasons'
    permission_required = set()

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'data': self.request.POST.copy()})
        return kwargs

    def get_formset(self):
        FormSet = formset_factory(
            self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs
        )
        return FormSet(**self.get_formset_kwargs())

    def get_region_name(self):
        # The region will get the same custom name as the catchment
        if self.object:
            return self.object.name

    def create_region_borders(self):
        geoms = [form['region'].borders.geom for form in self.formset.cleaned_data if 'region' in form]
        new_geom = geoms[0]
        for geom in geoms[1:]:
            new_geom = new_geom.union(geom)
        new_geom.normalize()
        if not type(new_geom) == MultiPolygon:
            new_geom = MultiPolygon(new_geom)
        return GeoPolygon.objects.create(geom=new_geom)

    def get_region(self):
        return Region.objects.create(
            name=self.get_region_name(),
            borders=self.create_region_borders()
        )

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        kwargs['formset_helper'] = self.formset_helper_class
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        self.formset = self.get_formset()
        if not self.formset.is_valid():
            return self.form_invalid(form)
        else:
            response = super().form_valid(form)
            self.object.region = self.get_region()
            self.object.type = 'custom'
            self.object.save()
            return response


class CatchmentUpdateView(OwnedObjectUpdateView):
    model = Catchment
    form_class = CatchmentModelForm
    permission_required = 'maps.change_catchment'


class CatchmentModalDeleteView(OwnedObjectModalDeleteView):
    model = Catchment
    success_url = reverse_lazy('catchment-list')
    success_message = 'deletion successful'
    permission_required = 'maps.delete_catchment'


# ----------- Catchment utilities---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = Catchment.objects.filter(Q(owner=self.request.user) | Q(publication_status='published'))
        else:
            qs = Catchment.objects.filter(publication_status='published')
        qs = qs.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- Region Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Region.objects.all().order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class NutsRegionAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):

        qs = NutsRegion.objects.all()

        levl_code = self.forwarded.get('levl_code', None)
        if levl_code is not None:
            qs = qs.filter(levl_code=levl_code)

        parent = self.forwarded.get('parent', None)
        if parent:
            qs = qs.filter(parent_id=parent)

        grandparent = self.forwarded.get('grandparent', None)
        if grandparent:
            qs = qs.filter(parent__parent_id=grandparent)

        great_grandparent = self.forwarded.get('great_grandparent', None)
        if great_grandparent:
            qs = qs.filter(parent__parent__parent_id=great_grandparent)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs.order_by('name')


class RegionOfLauAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Region.objects.filter(pk__in=Subquery(LauRegion.objects.all().values('pk'))).order_by('name')
        if self.q:
            qs = qs.filter(Q(name__icontains=self.q) | Q(lauregion__lau_id__contains=self.q))
        return qs


class CatchmentGeometryAPI(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        catchment_id = request.query_params.get('catchment', None)
        if catchment_id:
            catchment = get_object_or_404(Catchment, id=int(catchment_id))
            regions = Region.objects.filter(id=catchment.region_id)
            serializer = RegionGeoFeatureModelSerializer(regions, many=True)
            return Response({'geoJson': serializer.data})
        return Response({})


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
            serializer = RegionGeoFeatureModelSerializer(regions, many=True)
            return JsonResponse({'geoJson': serializer.data})

        return JsonResponse({})


# ----------- NutsRegions ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class NutsRegionSummaryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        obj = NutsRegion.objects.filter(id=request.query_params.get('id'))
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
            serializer = RegionGeoFeatureModelSerializer(regions, many=True)
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


class NutsRegionMapView(GeoDataSetDetailView):
    model_name = 'NutsRegion'
    template_name = 'nuts_region_map.html'
    filterset_class = NutsRegionFilterSet
    map_title = 'NUTS Regions'
    load_region = False
    load_catchment = False
    load_features = False
    feature_url = reverse_lazy('data.nutsregion')
    feature_summary_url = reverse_lazy('data.nutsregion-summary')
    region_url = reverse_lazy('data.nutsregion')
    adjust_bounds_to_features = True
    feature_layer_style = {
        'color': '#4061d2',
    }


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
    model = Attribute
    permission_required = set()


class AttributeCreateView(OwnedObjectCreateView):
    form_class = AttributeModelForm
    success_url = reverse_lazy('attribute-list')
    permission_required = 'maps.add_attribute'


class AttributeModalCreateView(OwnedObjectModalCreateView):
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
    model = Attribute
    form_class = AttributeModelForm
    permission_required = 'maps.change_attribute'


class AttributeModalUpdateView(OwnedObjectModalUpdateView):
    model = Attribute
    form_class = AttributeModalModelForm
    permission_required = 'maps.change_attribute'


class AttributeModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Attribute
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('attribute-list')
    permission_required = 'maps.delete_attribute'


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class RegionAttributeValueListView(OwnedObjectListView):
    model = RegionAttributeValue
    permission_required = set()


class RegionAttributeValueCreateView(OwnedObjectCreateView):
    form_class = RegionAttributeValueModelForm
    success_url = reverse_lazy('regionattributevalue-list')
    permission_required = 'maps.add_regionattributevalue'


class RegionAttributeValueModalCreateView(OwnedObjectModalCreateView):
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
    model = RegionAttributeValue
    form_class = RegionAttributeValueModelForm
    permission_required = 'maps.change_regionattributevalue'


class RegionAttributeValueModalUpdateView(OwnedObjectModalUpdateView):
    model = RegionAttributeValue
    form_class = RegionAttributeValueModalModelForm
    permission_required = 'maps.change_regionattributevalue'


class RegionAttributeValueModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = RegionAttributeValue
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('regionattributevalue-list')
    permission_required = 'maps.delete_regionattributevalue'


class RegionChildCatchmentOptions(OwnedObjectModelSelectOptionsView):
    model = Catchment
