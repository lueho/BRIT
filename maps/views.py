from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.views.generic.edit import FormMixin
from rest_framework.views import APIView
from django.db.models import Sum

from .forms import (
    CatchmentModelForm,
    CatchmentQueryForm,
    NutsMapFilterForm
)
from .models import (
    Catchment,
    GeoDataset,
    Region,
    NutsRegion
)
from maps.serializers import CatchmentSerializer, RegionSerializer, NutsRegionGeometrySerializer


class MapsListView(ListView):
    template_name = 'maps_list.html'

    def get_queryset(self):
        user_groups = self.request.user.groups.all()
        return GeoDataset.objects.filter(Q(visible_to_groups__in=user_groups) | Q(publish=True))


# ----------- Catchment ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentBrowseView(FormMixin, ListView):
    model = Catchment
    form_class = CatchmentQueryForm
    template_name = 'catchment_list.html'
    region_url = reverse_lazy('ajax_region_geometries')
    feature_url = reverse_lazy('ajax_catchment_geometries')
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

class GeoDatasetDetailView(DetailView):
    feature_url = None
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
                'load_features': self.load_features,
                'adjust_bounds_to_features': self.adjust_bounds_to_features,
                'region_id': self.object.region.id,
                'load_region': self.load_region,
                'markerStyle': self.marker_style
            }
        })
        return context

    def get_form(self):
        if self.form_class is not None:
            return self.form_class
        if self.filter_class is not None:
            return self.filter_class(self.request.GET).form

    def get_filter_fields(self):
        return {key: type(value.field.widget).__name__ for key, value in self.filter_class.base_filters.items()}

    def get_form_fields(self):
        if self.form_class is None and self.filter_class is not None:
            return self.get_filter_fields()
        return {key: type(value.widget).__name__ for key, value in self.form_class.base_fields.items()}


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
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


class RegionGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        if 'region_id' in request.query_params:
            region_id = request.query_params.get('region_id')
            regions = Region.objects.filter(id=region_id)
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


def is_valid_queryparam(param):
    return param != '' and param is not None


class NutsRegionAPIView(APIView):

    @staticmethod
    def get(request):
        qs = NutsRegion.objects.all()

        levl_code = int(request.query_params['levl_code'])
        if is_valid_queryparam(levl_code):
            qs = qs.filter(levl_code=levl_code)
        cntr_codes = request.query_params.getlist('cntr_code[]')
        if is_valid_queryparam(cntr_codes):
            qs = qs.filter(cntr_code__in=cntr_codes)

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
