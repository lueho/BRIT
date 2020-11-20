from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, View, UpdateView
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import FormMixin, ModelFormMixin
from rest_framework.views import APIView

from flexibi_dst.views import DualUserListView
from layer_manager.models import Layer
from .forms import (
    CatchmentForm,
    CatchmentQueryForm,
    MaterialModelForm,
    MaterialComponentModelForm,
    ScenarioModelForm,
    ScenarioInventoryConfigurationAddForm,
    ScenarioInventoryConfigurationUpdateForm,
    SeasonalDistributionModelForm,
)
from .models import (
    Catchment,
    Scenario,
    ScenarioInventoryConfiguration,
    Material,
    MaterialComponent,
    GeoDataset,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Region,
    ScenarioStatus,
)
from .serializers import CatchmentSerializer, BaseResultMapSerializer, RegionSerializer
from .tasks import run_inventory


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentBrowseView(FormMixin, ListView):
    model = Catchment
    form_class = CatchmentQueryForm
    template_name = 'catchment_list.html'


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


def load_catchment_options(request):
    if request.GET.get('region_id'):
        region = Region.objects.get(id=request.GET.get('region_id'))
        catchment_owners = []
        if int(request.GET.get('category_standard')):
            catchment_owners.append(User.objects.get(username=settings.PUBLIC_OBJECT_OWNER))
        if int(request.GET.get('category_custom')) and request.user.is_authenticated:
            catchment_owners.append(request.user)
        catchments = Catchment.objects.filter(region=region, owner__in=catchment_owners)
    else:
        catchments = Catchment.objects.none()
    return render(request, 'catchment_dropdown_list_options.html', {'catchments': catchments})


class CatchmentGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        print(self.request.GET.get('catchment_id'))
        catchments = Catchment.objects.filter(id=self.request.GET.get('catchment_id'))
        serializer = CatchmentSerializer(catchments, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)


# ----------- Materials/Feedstocks -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListView(DualUserListView):
    model = Material
    template_name = 'material_list.html'


class MaterialCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialModelForm
    template_name = 'material_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('material_detail', kwargs={'pk': self.object.pk})


class MaterialDetailView(DetailView):
    model = Material
    template_name = 'material_detail.html'
    object = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context['grouped_components'] = self.object.grouped_components()
        return self.render_to_response(context)


class MaterialUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Material
    form_class = MaterialModelForm
    template_name = 'material_update.html'
    success_url = '/scenario_builder/materials/{id}'

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('pk'))
        return material.owner == self.request.user


class MaterialDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Material
    template_name = 'material_delete.html'
    success_url = '/scenario_builder/materials'

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('pk'))
        return material.owner == self.request.user


class MaterialComponentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_create.html'
    object = None

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == material.owner

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.material = Material.objects.get(id=self.kwargs.get('pk'))
        self.object = form.save()
        return redirect('material_detail', pk=self.kwargs.get('pk'))


class MaterialComponentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_update.html'
    object = None

    def get_object(self, **kwargs):
        return MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))

    def test_func(self):
        component = MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))
        return self.request.user == component.owner

    def form_valid(self, form):
        self.object = form.save()
        return redirect('material_detail', pk=self.kwargs.get('pk'))


class MaterialComponentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponent
    template_name = 'material_component_delete.html'
    success_url = '/scenario_builder/materials/{material_id}'

    def get_object(self, **kwargs):
        return MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))

    def test_func(self):
        component = MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))
        return self.request.user == component.owner


class SeasonalDistributionCreateView(LoginRequiredMixin, CreateView):
    form_class = SeasonalDistributionModelForm
    template_name = 'seasonal_distribution_create.html'
    success_url = '/scenario_builder/materials/{material_id}'


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


# ----------- Scenarios ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class ScenarioListView(DualUserListView):
    model = Scenario
    template_name = 'scenario_list.html'


class ScenarioCreateView(LoginRequiredMixin, CreateView):
    model = Scenario
    form_class = ScenarioModelForm
    template_name = 'scenario_create.html'
    success_url = reverse_lazy('scenario_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class ScenarioUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Scenario
    template_name = 'scenario_create.html'
    form_class = ScenarioModelForm

    def get_success_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.object.id})

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner


class ScenarioDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Scenario
    template_name = 'scenario_delete.html'
    success_url = '/scenario_builder/scenarios'

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner


def get_evaluation_status(request, scenario_id=None, task_id=None):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result,
        "task_info": task_result.info
    }
    return JsonResponse(result, status=200)


class ScenarioDetailView(UserPassesTestMixin, DetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    template_name = 'scenario_detail.html'
    object = None
    config = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context['config'] = self.config
        context['static'] = self.object.owner.username == 'flexibi'
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        run_inventory(scenario.id)
        return redirect('scenario_result', scenario.id)

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner or scenario.owner.username == settings.PUBLIC_OBJECT_OWNER


class ScenarioAddInventoryAlgorithmView(LoginRequiredMixin, UserPassesTestMixin,
                                        TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationAddForm
    template_name = 'scenario_configuration_add.html'
    object = None

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner

    @staticmethod
    def post(request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        scenario = Scenario.objects.get(id=scenario_id)
        feedstock = Material.objects.get(id=request.POST.get('feedstock'))
        algorithm_id = request.POST.get('inventory_algorithm')
        algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
        parameters = algorithm.inventoryalgorithmparameter_set.all()
        values = {}
        for parameter in parameters:
            values[parameter] = []
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                values[parameter].append(InventoryAlgorithmParameterValue.objects.get(id=value_id))
        scenario.add_inventory_algorithm(feedstock, algorithm, values)
        return redirect('scenario_detail', pk=scenario_id)

    def get_object(self, **kwargs):
        return Scenario.objects.get(pk=self.kwargs.get('pk'))

    def get_initial(self):
        return {
            'feedstocks': self.object.available_feedstocks(),
            'scenario': self.object
        }

    def get_context_data(self, **kwargs):
        context = {'scenario': self.object,
                   'form': self.get_form()}
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioAlgorithmConfigurationUpdateView(LoginRequiredMixin, UserPassesTestMixin,
                                               TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationUpdateForm
    template_name = 'scenario_configuration_update.html'
    object = None

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        return self.request.user == scenario.owner

    @staticmethod
    def post(request, *args, **kwargs):
        scenario = Scenario.objects.get(id=request.POST.get('scenario'))
        current_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('current_algorithm'))
        feedstock = Material.objects.get(id=request.POST.get('feedstock'))
        scenario.remove_inventory_algorithm(current_algorithm, feedstock)
        new_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('inventory_algorithm'))
        parameters = new_algorithm.inventoryalgorithmparameter_set.all()
        values = {}
        for parameter in parameters:
            values[parameter] = []
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                values[parameter].append(InventoryAlgorithmParameterValue.objects.get(id=value_id))
        scenario.add_inventory_algorithm(feedstock, new_algorithm, values)
        return redirect('scenario_detail', pk=request.POST.get('scenario'))

    def get_object(self, **kwargs):
        return Scenario.objects.get(pk=self.kwargs.get('scenario_pk'))

    def get_initial(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        config = scenario.inventory_algorithm_config(algorithm)
        return config

    def get_context_data(self, **kwargs):
        context = self.get_initial()
        context['form'] = self.get_form()
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioRemoveInventoryAlgorithmView(LoginRequiredMixin, UserPassesTestMixin, View):
    scenario = None
    algorithm = None
    feedstock = None

    def test_func(self):
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        return self.scenario.owner == self.request.user

    def get(self, request, *args, **kwargs):
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        self.algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        self.feedstock = Material.objects.get(id=self.kwargs.get('feedstock_pk'))
        self.scenario.remove_inventory_algorithm(algorithm=self.algorithm, feedstock=self.feedstock)
        return redirect('scenario_detail', pk=self.scenario.id)


def load_geodataset_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock'):
        feedstock = Material.objects.get(id=request.GET.get('feedstock'))
        if request.GET.get('options') == 'create':
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock)
        elif request.GET.get('options') == 'update':
            current = GeoDataset.objects.filter(id=request.GET.get('current_geodataset'))
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock).union(current)
        else:
            geodatasets = scenario.available_geodatasets()
    else:
        geodatasets = GeoDataset.objects.none()
    return render(request, 'geodataset_dropdown_list_options.html', {'geodatasets': geodatasets})


def load_algorithm_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock') and request.GET.get('geodataset'):
        feedstock = Material.objects.get(id=request.GET.get('feedstock'))
        geodataset = GeoDataset.objects.get(id=request.GET.get('geodataset'))
        if request.GET.get('options') == 'create':
            algorithms = scenario.remaining_inventory_algorithm_options(feedstock, geodataset)
        elif request.GET.get('options') == 'update':
            current_algorithm = InventoryAlgorithm.objects.filter(id=request.GET.get('current_inventory_algorithm'),
                                                                  feedstock=feedstock, geodataset=geodataset)
            algorithms = scenario.remaining_inventory_algorithm_options(feedstock, geodataset).union(current_algorithm)
        else:
            algorithms = scenario.available_inventory_algorithms()
    else:
        algorithms = InventoryAlgorithm.objects.none()
    return render(request, 'algorithm_dropdown_list_options.html', {'algorithms': algorithms})


def load_parameter_options(request):
    if request.GET.get('inventory_algorithm'):
        algorithm = InventoryAlgorithm.objects.get(id=request.GET.get('inventory_algorithm'))
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
        context = {
            'parameters': {
                parameter: InventoryAlgorithmParameterValue.objects.filter(parameter=parameter) for parameter in
                parameters}}
        return render(request, 'parameters_dropdown_list_options.html', context)
    else:
        return HttpResponse("")


class ResultMapAPI(APIView):
    """Rest API to get features from automatically generated result tables. Endpoint for Leaflet maps"""

    @staticmethod
    def get(request, *args, **kwargs):
        layer = Layer.objects.get(table_name=kwargs['layer_name'])
        feature_collection = layer.get_feature_collection()
        features = feature_collection.objects.all()
        serializer_class = BaseResultMapSerializer
        serializer_class.Meta.model = feature_collection

        serializer = serializer_class(features, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
