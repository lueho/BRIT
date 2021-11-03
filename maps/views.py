from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.views.generic.edit import FormMixin
from rest_framework.views import APIView

from .forms import (
    CatchmentForm,
    CatchmentQueryForm,
)
from .models import (
    Catchment,
    GeoDataset,
    Region,
)
from maps.serializers import CatchmentSerializer, RegionSerializer


class MapsListView(ListView):
    queryset = GeoDataset.objects.all()
    template_name = 'maps_list.html'


# ----------- Catchment ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentBrowseView(FormMixin, ListView):
    model = Catchment
    form_class = CatchmentQueryForm
    template_name = 'catchment_list.html'

    def get_initial(self):
        initial = {}
        region_id = self.request.GET.get('region')
        catchment_id = self.request.GET.get('catchment')
        if catchment_id:
            catchment = Catchment.objects.get(id=catchment_id)
            initial['region'] = catchment.region.id
            initial['catchment'] = catchment.id
        elif region_id:
            initial['region'] = region_id
        return initial


class CatchmentCreateView(LoginRequiredMixin, CreateView):
    template_name = 'catchment_create.html'
    form_class = CatchmentForm
    success_url = reverse_lazy('catchment_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CatchmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Catchment
    form_class = CatchmentForm

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


class CatchmentGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        catchments = Catchment.objects.filter(id=self.request.GET.get('catchment_id'))
        serializer = CatchmentSerializer(catchments, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)


# ----------- Geodataset -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoDatasetDetailView(DetailView):
    feature_url = None
    region_url = reverse_lazy('ajax_region_geometries')
    filter_class = None
    form_class = None
    load_features = False
    marker_style = None
    model = GeoDataset
    template_name = 'maps_base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_header': self.object.name,
            'form': self.get_form(),
            'geodataset': self.object,
            'map_config': {
                'form_fields': self.get_form_fields(),
                'region_url': self.region_url,
                'feature_url': self.feature_url,
                'region_id': self.object.region.id,
                'load_features': self.load_features,
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
        return {key: type(value.field).__name__ for key, value in self.filter_class.base_filters.items()}

    def get_form_fields(self):
        if self.form_class is None and self.filter_class is not None:
            return self.get_filter_fields()
        return {key: type(value).__name__ for key, value in self.form_class.base_fields.items()}


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        regions = Region.objects.filter(id=self.request.GET.get('region_id'))
        serializer = RegionSerializer(regions, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
