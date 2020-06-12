from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, CreateView, DeleteView, DetailView, ListView, View, UpdateView
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import ModelFormMixin
from rest_framework.views import APIView

from layer_manager.models import Layer
from scenario_builder.scenarios import GisInventory
from .forms import (CatchmentForm, ScenarioModelForm, ScenarioInventoryConfigurationAddForm,
                    ScenarioInventoryConfigurationUpdateForm)
from .models import Catchment, Scenario, ScenarioInventoryConfiguration, Material, GeoDataset, InventoryAlgorithm, \
    InventoryAlgorithmParameter, InventoryAlgorithmParameterValue
from .serializers import CatchmentSerializer, BaseResultMapSerializer


class InventoryMixin(SingleObjectMixin):
    """
    A mixin that provides functionality for performing flexibi bioresource inventories
    """
    config = None
    object = None

    def get_inventory_config(self, obj):
        config_queryset = ScenarioInventoryConfiguration.objects.filter(scenario=self.object)

        inventory_config = {}
        for entry in config_queryset:
            function = entry.inventory_algorithm.function_name
            parameter = entry.inventory_parameter.short_name
            value = entry.inventory_value.value

            if function not in inventory_config:
                inventory_config[function] = {}
            if parameter not in inventory_config[function]:
                inventory_config[function][parameter] = value

        return inventory_config

    @staticmethod
    def reformat_inventory_config(inventory_config):
        inventory_config_list = []
        for algorithm_name, parameter_dict in inventory_config.items():
            parameter_list = []
            for parameter, value in inventory_config[algorithm_name].items():
                parameter_list.append({'function_name': parameter,
                                       'value': value})
            inventory_config_list.append({'algorithm': algorithm_name,
                                          'parameters': parameter_list})
        return inventory_config_list


class ScenarioListView(ListView):
    model = Scenario


class ScenarioCreateView(CreateView):
    model = Scenario
    form_class = ScenarioModelForm
    success_url = reverse_lazy('scenarios')


class ScenarioUpdateView(UpdateView):
    model = Scenario
    form_class = ScenarioModelForm

    def get_success_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.object.id})


class ScenarioDeleteView(DeleteView):
    template_name = 'scenario_builder/scenario_delete.html'

    def get_object(self, **kwargs):
        scenario_id = self.kwargs.get('pk')
        return Scenario.objects.get(id=scenario_id)

    def get_success_url(self):
        return reverse_lazy('scenario_list')


class ScenarioDetailView(InventoryMixin, DetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    template_name = 'scenario_builder/scenario_detail.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context['config'] = self.config
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        inventory = GisInventory(self.object)
        inventory.run()
        return self.get(request, *args, **kwargs)


class ScenarioAddInventoryAlgorithmView(TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationAddForm
    template_name = 'scenario_builder/scenario_configuration_add.html'
    object = None

    @staticmethod
    def post(request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        scenario = Scenario.objects.get(id=scenario_id)
        algorithm_id = request.POST.get('inventory_algorithm')
        algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
        values = []
        for parameter in parameters:
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                values.append(InventoryAlgorithmParameterValue.objects.get(id=value_id))
        scenario.add_inventory_algorithm(algorithm, values)
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


class ScenarioAlgorithmConfigurationUpdateView(TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationUpdateForm
    template_name = 'scenario_builder/scenario_configuration_update.html'
    object = None

    @staticmethod
    def post(request, *args, **kwargs):
        scenario = Scenario.objects.get(id=request.POST.get('scenario'))
        current_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('current_algorithm'))
        scenario.remove_inventory_algorithm(current_algorithm)
        new_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('inventory_algorithm'))
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=new_algorithm)
        values = []
        for parameter in parameters:
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                value = InventoryAlgorithmParameterValue.objects.get(id=value_id)
                values.append(value)
        scenario.add_inventory_algorithm(new_algorithm, values)
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


def remove_algorithm_from_scenario(request, scenario_pk, algorithm_pk):
    scenario = Scenario.objects.get(id=scenario_pk)
    algorithm = InventoryAlgorithm.objects.get(id=algorithm_pk)
    scenario.remove_inventory_algorithm(algorithm)
    return redirect('scenario_detail', pk=scenario_pk)


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
    return render(request, 'scenario_builder/geodataset_dropdown_list_options.html', {'geodatasets': geodatasets})


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
    return render(request, 'scenario_builder/algorithm_dropdown_list_options.html', {'algorithms': algorithms})


def load_parameter_options(request):
    if request.GET.get('inventory_algorithm'):
        algorithm = InventoryAlgorithm.objects.get(id=request.GET.get('inventory_algorithm'))
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
        context = {
            'parameters': {
                parameter: InventoryAlgorithmParameterValue.objects.filter(parameter=parameter) for parameter in
                parameters}}
        return render(request, 'scenario_builder/parameters_dropdown_list_options.html', context)
    else:
        return HttpResponse("")


class FeedstockDefinitionView(TemplateView):
    template_name = 'feedstock_definition.html'


class CatchmentDefinitionView(CreateView):
    template_name = 'catchment_definition.html'
    form_class = CatchmentForm
    success_url = reverse_lazy('catchment_view')


class CatchmentDeleteView(DeleteView):
    model = Catchment
    success_url = reverse_lazy('catchment_view')


# class CatchmentView(TemplateView):
# template_name = 'catchment_view.html'
# form_class = CatchmentForm
# success_url = reverse_lazy('catchment_view')


def catchmentView(request):
    catchment_names = Catchment.objects.all().values('name')

    return render(request, 'catchment_view.html', {'names': catchment_names})


def catchmentDelete(request):
    return redirect(catchmentView)


class ResultMapAPIView(APIView):
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


class CatchmentAPIView(APIView):

    @staticmethod
    def get(request):
        name = request.GET.get('function_name')
        qs = Catchment.objects.filter(name=name)

        serializer = CatchmentSerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
