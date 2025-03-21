from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.gis.geos import MultiPolygon
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q, Subquery
from django.forms import formset_factory
from django.http import JsonResponse
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin
from django_filters.views import FilterView
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.views import APIView, Response

from maps.serializers import (CatchmentGeoFeatureModelSerializer, LauRegionOptionSerializer, LauRegionSummarySerializer,
                              MapConfigurationSerializer,
                              NutsRegionCatchmentOptionSerializer, NutsRegionOptionSerializer,
                              NutsRegionSummarySerializer, RegionGeoFeatureModelSerializer)
from utils.forms import DynamicTableInlineFormSetHelper
from utils.views import (BRITFilterView, OwnedObjectCreateView, OwnedObjectListView, OwnedObjectModalCreateView,
                         OwnedObjectModalDeleteView, OwnedObjectModalDetailView, OwnedObjectModalUpdateView,
                         OwnedObjectModelSelectOptionsView, PublishedObjectFilterView, UserCreatedObjectDetailView,
                         UserCreatedObjectUpdateView, UserOwnedObjectFilterView)
from .filters import CatchmentFilterSet, GeoDataSetFilterSet, NutsRegionFilterSet, RegionFilterSet
from .forms import (AttributeModalModelForm, AttributeModelForm, CatchmentCreateDrawCustomForm,
                    CatchmentCreateMergeLauForm, CatchmentModelForm, GeoDataSetModelForm, LocationModelForm,
                    RegionAttributeValueModalModelForm, RegionAttributeValueModelForm, RegionMergeForm,
                    RegionMergeFormSet, RegionModelForm)
from .models import (Attribute, Catchment, GeoDataset, GeoPolygon, LauRegion, Location, MapConfiguration,
                     ModelMapConfiguration, NutsRegion, Region, RegionAttributeValue)


class MapMixin:
    """
    Mixin to add 'map_config' to the context.
    Retrieves MapConfiguration based on the view type and context.
    """

    map_config_related_name = 'map_configuration'
    map_title = None
    model_name = None
    features_layer_api_basename = None
    api_prefix = 'api-'
    api_geom_suffix = '-geojson'

    def get_map_title(self):
        """
        Retrieves the title of the map.
        Override this method in child classes for custom retrieval logic.
        """
        return self.map_title

    def get_catchment_feature_id(self):
        """Override to provide a custom catchment ID"""
        if hasattr(self, 'object'):
            if hasattr(self.object, 'catchment'):
                if isinstance(self.object.catchment, Catchment):
                    return self.object.catchment.id
        return None

    def get_region_feature_id(self):
        """Override to provide a custom region ID"""
        if hasattr(self, 'object'):
            if hasattr(self.object, 'region'):
                if isinstance(self.object.region, Region):
                    return self.object.region.id
        return None

    def get_features_feature_id(self):
        """Override to provide a custom feature ID"""
        return None

    def get_features_geometries_url(self):
        if self.features_layer_api_basename:
            try:
                return reverse(f'{self.features_layer_api_basename}{self.api_geom_suffix}')
            except NoReverseMatch:
                return None
        return None

    def get_features_layer_details_url_template(self):
        if self.features_layer_api_basename:
            try:
                template = reverse(
                    f'{self.features_layer_api_basename}-detail',
                    kwargs={'pk': None}
                ).replace('None', '').rstrip('/') + '/'
                return template
            except NoReverseMatch:
                return None
        return None

    def get_features_layer_summary_url(self):
        if self.features_layer_api_basename:
            try:
                return reverse(f'{self.features_layer_api_basename}-summaries')
            except NoReverseMatch:
                return None
        return None

    def get_map_configuration(self):
        """
        Retrieves the appropriate MapConfiguration instance.
        Override this method in child classes for custom retrieval logic.
        """

        # If the object has a MapConfiguration assigned to it by attribute, use it
        if hasattr(self, 'object') and self.object:
            try:
                return getattr(self.object, self.map_config_related_name)
            except AttributeError:
                pass

        # If a model is given (e.g. in a DetailView), which has a MapConfiguration, use it
        if hasattr(self, 'model') and self.model:
            self.model_name = self.model.__name__
            try:
                model_config = ModelMapConfiguration.objects.get(model_name=self.model_name)
                return model_config.map_config
            except ModelMapConfiguration.DoesNotExist:
                pass

        # If the model is not explicitly given (e.g. in a FilterView), find the model based on the FilterSet
        if hasattr(self, 'filterset_class') and self.filterset_class:
            self.model_name = self.filterset_class.Meta.model.__name__
            try:
                model_config = ModelMapConfiguration.objects.get(model_name=self.model_name)
                return model_config.map_config
            except ModelMapConfiguration.DoesNotExist:
                pass

        # Alternatively, determine MapConfiguration based on request or other logic
        # For example, based on query parameters
        map_config_id = self.request.GET.get('map_config_id')
        if map_config_id:
            try:
                return MapConfiguration.objects.get(id=map_config_id)
            except MapConfiguration.DoesNotExist:
                pass

        # If no MapConfiguration is found, fall back to default. While the default has api_basenames for the region
        # and the catchment layer, the api_basename for the features layer is not set and needs to be found.

        # If the api_basename is not found via MapConfiguration instance and is not set explicitly but the view has a
        # model associated with it, try to find the API by naming convention.
        if not self.features_layer_api_basename and self.model_name:
            api_basename_candidate = f'{self.api_prefix}{self.model_name.lower()}'
            try:
                reverse(f'{api_basename_candidate}{self.api_geom_suffix}')
                self.features_layer_api_basename = api_basename_candidate
            except NoReverseMatch:
                pass

        return MapConfiguration.objects.get(name='Default Map Configuration')

    def get_override_params(self):
        params = {}

        # If filter parameters are set, assume that features should be loaded.
        if self.request.GET:
            params['load_features'] = True

        # Previous assumption can be overridden by explicitly setting the load_features parameter.
        for key in ['load_region', 'load_catchment', 'load_features']:
            value = self.request.GET.get(key)
            if value:
                params[key] = value == 'true'

        # In case no filter parameters are set, use the default load_<layer_type> values defined in the layer configurations.

        if self.get_region_feature_id():
            params['region_feature_id'] = self.get_region_feature_id()

        if self.get_catchment_feature_id():
            params['catchment_feature_id'] = self.get_catchment_feature_id()

        if self.get_features_feature_id():
            params['features_feature_id'] = self.get_features_feature_id()

        if self.get_features_geometries_url():
            params['features_geometries_url'] = self.get_features_geometries_url()

        if self.get_features_layer_details_url_template():
            params['features_layer_details_url_template'] = self.get_features_layer_details_url_template()

        if self.get_features_layer_summary_url():
            params['features_layer_summary_url'] = self.get_features_layer_summary_url()

        if hasattr(self, 'object'):
            params['features_feature_id'] = getattr(self.object, 'pk', None)

        return params

    def get_map_config_serialized(self):
        """
        Serializes the MapConfiguration instance.
        Returns JSON data or None if no MapConfiguration is found.
        """
        map_config = self.get_map_configuration()
        if map_config:
            serializer = MapConfigurationSerializer(
                map_config,
                context={
                    'request': self.request,
                    'override_params': self.get_override_params()
                },
            )
            return serializer.data
        return None

    def post_process_map_config(self, map_config):
        """
        Override this method to post-process the map configuration before returning it.
        """
        if not map_config.get('regionId') or not map_config.get('regionLayerGeometriesUrl'):
            map_config['loadRegion'] = False
        if not map_config.get('catchmentId') or not map_config.get('catchmentLayerGeometriesUrl'):
            map_config['loadCatchment'] = False
        if not map_config.get('featuresLayerGeometriesUrl'):
            map_config['loadFeatures'] = False
        return map_config

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_title': self.get_map_title(),
            'map_config': self.post_process_map_config(self.get_map_config_serialized()),
        })
        return context


class MapsDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'maps_dashboard.html'
    permission_required = set()


# ----------- Geodataset -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


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


# ----------- GeoDataSet CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GeoDataSetListView(OwnedObjectListView):
    model = GeoDataset
    permission_required = set()


class GeoDataSetCreateView(OwnedObjectCreateView):
    model = GeoDataset
    form_class = GeoDataSetModelForm
    permission_required = 'maps.add_geodataset'


class GeoDataSetFilteredMapView(MapMixin, FilterView):
    model_name = None  # TODO: Remove this for pk
    template_name = 'filtered_map.html'

    def get_dataset(self):
        try:
            return GeoDataset.objects.get(model_name=self.model_name)
        except GeoDataset.DoesNotExist:
            raise ImproperlyConfigured(f'No GeoDataset with model_name {self.model_name} found.')

    def get_region_feature_id(self):
        return self.get_dataset().region_id

    def get_map_configuration(self):
        dataset = self.get_dataset()
        if dataset.map_configuration:
            return dataset.map_configuration
        else:
            return MapConfiguration.objects.get(name='Default Map Configuration')

    # def get_dataset(self):
    #     return GeoDataset.objects.get(pk=self.kwargs.get('pk')) # TODO: Implement this functionality


class GeoDataSetUpdateView(UserCreatedObjectUpdateView):
    model = GeoDataset
    form_class = GeoDataSetModelForm


class GeoDataSetModalDeleteView(OwnedObjectModalDeleteView):
    model = GeoDataset
    success_url = reverse_lazy('geodataset-list')
    success_message = 'deletion successful'
    permission_required = 'maps.delete_geodataset'


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LocationListView(OwnedObjectListView):
    model = Location
    permission_required = set()


class LocationCreateView(OwnedObjectCreateView):
    model = Location
    form_class = LocationModelForm
    permission_required = 'maps.add_location'


class LocationDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Location


class LocationUpdateView(UserCreatedObjectUpdateView):
    model = Location
    form_class = LocationModelForm


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


class RegionMapView(LoginRequiredMixin, MapMixin, FilterView):
    template_name = 'region_map.html'
    filterset_class = RegionFilterSet
    map_title = 'Regions'


class RegionDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Region
    features_layer_api_basename = 'api-region'


class RegionCreateView(OwnedObjectCreateView):
    model = Region
    form_class = RegionModelForm
    permission_required = 'maps.add_region'


class RegionUpdateView(UserCreatedObjectUpdateView):
    model = Region
    form_class = RegionModelForm


class RegionModalDeleteView(OwnedObjectModalDeleteView):
    model = Region
    success_url = reverse_lazy('region-list')
    success_message = 'deletion successful'
    permission_required = 'maps.delete_region'


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedCatchmentListView(PublishedObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilterSet
    ordering = 'name'


class UserOwnedCatchmentListView(UserOwnedObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilterSet
    ordering = 'name'


class CatchmentDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Catchment


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
        geoms = [
            form.get('region').borders.geom
            for form in self.formset.cleaned_data
            if form.get('region') is not None
        ]
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
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.region = self.get_region()
            self.object.type = 'custom'
            self.object.save()
        return response


class CatchmentUpdateView(UserCreatedObjectUpdateView):
    model = Catchment
    form_class = CatchmentModelForm


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
            serializer = CatchmentGeoFeatureModelSerializer(qs, many=True)
            return JsonResponse({'geoJson': serializer.data})


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


class NutsRegionMapView(GeoDataSetFilteredMapView):
    model_name = 'NutsRegion'
    template_name = 'nuts_region_map.html'
    filterset_class = NutsRegionFilterSet
    features_layer_api_basename = 'api-nuts-region'
    map_title = 'NUTS Regions'


class NutsRegionParentsDetailAPI(APIView):
    """
    API to fetch all parent levels of a specific NUTS region.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            region = NutsRegion.objects.get(pk=pk)
        except NutsRegion.DoesNotExist:
            raise NotFound('A NUTS region with the provided ID does not exist.')

        data = {}
        current_region = region

        for lvl in range(current_region.levl_code - 1, -1, -1):
            if current_region.parent:
                current_region = current_region.parent
                serializer = NutsRegionOptionSerializer(current_region)
                data[f'level_{lvl}'] = serializer.data
            else:
                break  # No more parents available

        return Response(data)


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


class AttributeDetailView(UserCreatedObjectDetailView):
    template_name = 'attribute_detail.html'
    model = Attribute


class AttributeModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Attribute
    permission_required = set()


class AttributeUpdateView(UserCreatedObjectUpdateView):
    model = Attribute
    form_class = AttributeModelForm


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


class RegionAttributeValueDetailView(UserCreatedObjectDetailView):
    model = RegionAttributeValue


class RegionAttributeValueModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = RegionAttributeValue
    permission_required = set()


class RegionAttributeValueUpdateView(UserCreatedObjectUpdateView):
    model = RegionAttributeValue
    form_class = RegionAttributeValueModelForm


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
