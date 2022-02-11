from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, TemplateView
from django.views.generic.edit import FormMixin
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.views import APIView, Response

from maps.serializers import RegionSerializer, CatchmentSerializer, NutsRegionGeometrySerializer, \
    NutsRegionOptionSerializer, LauRegionOptionSerializer
from .forms import (
    CatchmentModelForm,
    CatchmentQueryForm,
    NutsMapFilterForm,
    NutsRegionQueryForm
)
from .models import (
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
        return GeoDataset.objects.filter(Q(visible_to_groups__in=user_groups) | Q(publish=True))


# ----------- Catchment ------------------------------------------------------------------------------------------------
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


# ----------- Geodataset -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoDatasetDetailView(FormMixin, DetailView):
    feature_url = None
    feature_popup_url = None
    region_url = reverse_lazy('ajax_region_geometries')
    filter_class = None
    form_class = None
    load_features = False
    adjust_bounds_to_features = False
    load_region = True
    marker_style = None
    model = GeoDataset
    template_name = 'maps_base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_header': self.object.name,
            'form': self.get_form(),
            'map_config': {
                'form_fields': self.get_form_fields(),
                'region_url': self.region_url,
                'feature_url': self.feature_url,
                'feature_popup_url': self.feature_popup_url,
                'load_features': self.get_load_features(),
                'adjust_bounds_to_features': self.adjust_bounds_to_features,
                'region_id': self.object.region.id,
                'load_region': self.load_region,
                'markerStyle': self.marker_style
            }
        })
        return context

    def get_form(self, form_class=None):
        if self.form_class is not None:
            return self.form_class(**self.get_form_kwargs())
        if self.filter_class is not None:
            return self.filter_class(self.request.GET).form

    def get_filter_fields(self):
        return {key: type(value.field.widget).__name__ for key, value in self.filter_class.base_filters.items()}

    def get_form_fields(self):
        if self.form_class is None and self.filter_class is not None:
            return self.get_filter_fields()
        return {key: type(value.widget).__name__ for key, value in self.form_class.base_fields.items()}

    def get_load_features(self):
        if self.request.GET.get('load_features'):
            return self.request.GET.get('load_features') == 'true'
        else:
            return self.load_features


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentGeometryAPI(APIView):

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

    @staticmethod
    def get(request, *args, **kwargs):
        if 'region_id' in request.query_params:
            region_id = request.query_params.get('region_id')
            regions = Region.objects.filter(id=region_id)
            serializer = RegionSerializer(regions, many=True)
            return JsonResponse({'geoJson': serializer.data})

        return JsonResponse({})


class CatchmentRegionGeometryAPI(APIView):
    """
    Similar to RegionGeometryAPI. Instead of taking the id of the requested region, this takes a catchment id as input
    and returns the geometry of the associated Region.
    """

    @staticmethod
    def get(request, *args, **kwargs):
        if 'region_id' in request.query_params:
            region_id = request.query_params.get('region_id')
            catchment = Catchment.objects.get(id=region_id)
            regions = Region.objects.filter(catchment=catchment)
            serializer = RegionSerializer(regions, many=True)
            return JsonResponse({'geoJson': serializer.data})

        return JsonResponse({})


# ----------- NUTS Map -------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NutsMapView(GeoDatasetDetailView):
    feature_url = reverse_lazy('data.nuts_regions')
    form_class = NutsMapFilterForm
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

    @staticmethod
    def get(request):
        qs = NutsRegion.objects.all()

        if 'levl_code' in request.query_params:
            qs = qs.filter(levl_code=request.query_params['levl_code'])
        if 'cntr_code[]' in request.query_params:
            qs = qs.filter(cntr_code__in=request.query_params.getlist('cntr_code[]'))
        if 'parent_id' in request.query_params:
            qs = qs.filter(parent_id=request.query_params['parent_id'])

        serializer = NutsRegionGeometrySerializer(qs, many=True)
        region_count = len(serializer.data['features'])
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'region_count': {
                    'label': 'Number of selected regions',
                    'value': str(region_count),
                },
            }
        }

        return JsonResponse(data, safe=False)


class NutsRegionPedigreeAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    @staticmethod
    def get(request):

        if 'id' not in request.query_params:
            raise ParseError('Query parameter "id" missing. Must provide valid id of NUTS region.')

        if 'direction' not in request.query_params or request.query_params['direction'] not in ('children', 'parents'):
            raise ParseError('Missing or wrong query parameter "direction". Options: "parents", "children"')

        try:
            catchment = Catchment.objects.get(id=request.query_params['id'])
            instance = catchment.region.nutsregion
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
            data['id_level_4'] = []
            if instance.levl_code == 3:
                qs = LauRegion.objects.filter(nuts_parent=instance)
                serializer = LauRegionOptionSerializer(qs, many=True)
                data[f'id_level_4'] = serializer.data

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
                serializer = NutsRegionOptionSerializer(qs, many=True)
                data[f'id_level_{lvl}'] = serializer.data
            data['id_level_4'] = []
            if instance.levl_code == 3:
                qs = LauRegion.objects.filter(nuts_parent=instance)
                serializer = LauRegionOptionSerializer(qs, many=True)
                data[f'id_level_4'] = serializer.data

        if request.query_params['direction'] == 'parents':
            for lvl in range(instance.levl_code - 1, -1, -1):
                instance = instance.parent
                serializer = NutsRegionOptionSerializer(instance)
                data[f'id_level_{lvl}'] = serializer.data

        return Response(data)
