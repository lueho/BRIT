from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, FormView, UpdateView, View
from rest_framework.views import APIView

from flexibi_dst.views import DualUserListView
from material_manager.models import Material
from .forms import (GreenhouseModelForm,
                    GreenhouseGrowthCycle,
                    GreenhouseGrowthCycleModelForm,
                    AddGreenhouseGrowthCycleModelForm,
                    UpdateGreenhouseGrowthCycleValuesForm,
                    NantesGreenhousesFilterForm)
from .models import Greenhouse, NantesGreenhouses
from .serializers import NantesGreenhousesGeometrySerializer


class GreenhouseListView(DualUserListView):
    model = Greenhouse
    template_name = 'greenhouse_list.html'


class GreenhouseCreateView(LoginRequiredMixin, CreateView):
    form_class = GreenhouseModelForm
    template_name = 'greenhouse_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.object.pk})


class GreenhouseDetailView(DetailView):
    model = Greenhouse
    template_name = 'greenhouse_detail.html'
    object = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context['growth_cycle_range'] = range(1, self.object.number_of_growth_cycles() + 1)
        context['grouped_growth_cycles'] = self.object.grouped_growth_cycles()
        return self.render_to_response(context)


class GreenhouseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Greenhouse
    form_class = GreenhouseModelForm
    template_name = 'greenhouse_update.html'
    success_url = '/scenario_builder/nantes/greenhouses/{id}'

    def test_func(self):
        material = Greenhouse.objects.get(id=self.kwargs.get('pk'))
        return material.owner == self.request.user


class GreenhouseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Greenhouse
    template_name = 'greenhouse_delete.html'
    success_url = '/scenario_builder/nantes/greenhouses'

    def test_func(self):
        material = Greenhouse.objects.get(id=self.kwargs.get('pk'))
        return material.owner == self.request.user


class GreenhouseAddGrowthCycleView(LoginRequiredMixin, UpdateView):
    model = Greenhouse
    form_class = AddGreenhouseGrowthCycleModelForm
    template_name = 'greenhouse_add_growth_cycle.html'
    object = None

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        material = Material.objects.get(id=request.POST.get('material'))
        self.object.add_growth_cycle(material)
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class GreenhouseRemoveGrowthCycleView(LoginRequiredMixin, UserPassesTestMixin, View):
    greenhouse = None
    cycle_number = None

    def get(self, request, *args, **kwargs):
        self.greenhouse = Greenhouse.objects.get(id=self.kwargs.get('greenhouse_pk'))
        self.cycle_number = self.kwargs.get('cycle_number')
        self.greenhouse.remove_growth_cycle(self.cycle_number)
        return redirect('greenhouse_detail', pk=self.greenhouse.id)

    def test_func(self):
        self.greenhouse = Greenhouse.objects.get(id=self.kwargs.get('greenhouse_pk'))
        return self.greenhouse.owner == self.request.user


class GreenhouseGrowthCycleCreateView(LoginRequiredMixin, CreateView):
    form_class = GreenhouseGrowthCycleModelForm
    template_name = 'greenhouse_growth_cycle_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.object.pk})


class UpdateGreenhouseGrowthCycleValuesView(LoginRequiredMixin, UpdateView):
    model = GreenhouseGrowthCycle
    form_class = UpdateGreenhouseGrowthCycleValuesForm
    template_name = 'greenhouse_growth_cycle_update_values.html'
    object = None

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_object(self, **kwargs):
        return GreenhouseGrowthCycle.objects.get(id=self.kwargs.get('cycle_pk'))

    def get_success_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.kwargs.get('pk')})

    def get_initial(self):
        return {
            'material': self.object.material,
            'component': self.object.component
        }


class NantesGreenhousesView(FormView):
    template_name = 'explore_nantes_greenhouses.html'
    form_class = NantesGreenhousesFilterForm
    initial = {'heated': 'Yes', 'lighted': 'Yes'}


class NantesGreenhousesAPIView(APIView):

    @staticmethod
    def get(request):
        qs = NantesGreenhouses.objects.all()

        if request.GET.get('lighting') == '2':
            qs = qs.filter(lighted=True)
        elif request.GET.get('lighting') == '3':
            qs = qs.filter(lighted=False)

        if request.GET.get('heating') == '2':
            qs = qs.filter(heated=True)
        elif request.GET.get('heating') == '3':
            qs = qs.filter(heated=False)

        if request.GET.get('prod_mode') == '2':
            qs = qs.filter(above_ground=False)
        elif request.GET.get('prod_mode') == '3':
            qs = qs.filter(above_ground=True)

        if request.GET.get('cult_man') == '2':
            qs = qs.filter(high_wire=False)
        elif request.GET.get('cult_man') == '3':
            qs = qs.filter(heated=True)

        crops = []
        if request.GET.get('cucumber') == 'true':
            crops.append('Cucumber')
        if request.GET.get('tomato') == 'true':
            crops.append('Tomato')

        qs = qs.filter(culture_1__in=crops)

        serializer = NantesGreenhousesGeometrySerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'gh_count': len(serializer.data['features']),
                'gh_surface': round(qs.aggregate(Sum('surface_ha'))['surface_ha__sum'], 1)
            }
        }

        return JsonResponse(data, safe=False)
