from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, CreateView, DeleteView, DetailView, ListView, View, UpdateView
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import ModelFormMixin
from rest_framework.views import APIView

from layer_manager.models import Layer
from scenario_builder.scenarios import GisInventory
from .forms import CatchmentForm, ScenarioModelForm, ScenarioInventoryConfigurationForm
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


class ScenarioDetailView(InventoryMixin, DetailView):
    """
    View to display the details of the setup of an inventory inside a scenario.
    """

    model = Scenario

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_as_dict()
        self.inventory_config_list = self.reformat_inventory_config(self.inventory_config)
        context = self.get_context_data(object=self.object)
        context['config'] = self.inventory_config_list
        return self.render_to_response(context)


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
        return reverse('scenario_configuration', kwargs={'pk': self.object.id})


class ScenarioDeleteView(DeleteView):
    template_name = 'scenario_builder/scenario_delete.html'

    def get_object(self, **kwargs):
        scenario_id = self.kwargs.get('pk')
        return Scenario.objects.get(id=scenario_id)

    def get_success_url(self):
        return reverse_lazy('scenario-list')


class ScenarioConfigurationView(InventoryMixin, DetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    template_name = 'scenario_builder/scenario_configuration_summary.html'

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
    form_class = ScenarioInventoryConfigurationForm
    template_name = 'scenario_builder/scenarioinventoryconfiguration_form.html'

    def post(self, request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        scenario = Scenario.objects.get(id=scenario_id)
        algorithm_id = request.POST.get('inventory_algorithm')
        algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
        values = []
        for parameter in parameters:
            if 'parameter_' + str(parameter.pk) in request.POST:
                values.append(request.POST.get('parameter_' + str(parameter.pk)))
        scenario.add_inventory_algorithm(algorithm, values)
        return redirect('scenario_configuration', pk=scenario_id)

    def get_object(self, **kwargs):
        return Scenario.objects.get(pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = {'scenario': self.object,
                   'form': self.get_form()}
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


def remove_algorithm_from_scenario(request, scenario_pk, algo_pk):
    scenario = Scenario.objects.get(id=scenario_pk)
    algorithm = InventoryAlgorithm.objects.get(id=algo_pk)
    scenario.remove_inventory_algorithm(algorithm)
    return redirect('scenario_configuration', pk=scenario_pk)


def load_feedstock_options(request):
    scenario_id = request.GET.get('scenario')
    scenario = Scenario.objects.get(id=scenario_id)
    feedstocks = scenario.available_feedstocks()
    return render(request, 'scenario_builder/feedstock_dropdown_list_options.html', {'feedstocks': feedstocks})


def load_geodataset_options(request):
    scenario_id = request.GET.get('scenario')
    scenario = Scenario.objects.get(id=scenario_id)
    region = scenario.region
    feedstock_id = request.GET.get('feedstock')
    feedstock = Material.objects.get(id=feedstock_id)
    algorithms = InventoryAlgorithm.objects.filter(feedstock=feedstock)
    geodatasets = GeoDataset.objects.filter(region=region, id__in=algorithms.values('geodataset_id'))
    return render(request, 'scenario_builder/geodataset_dropdown_list_options.html', {'geodatasets': geodatasets})


def load_algorithm_options(request):
    geodataset_id = request.GET.get('geodataset')
    geodataset = GeoDataset.objects.get(id=geodataset_id)
    algorithms = geodataset.inventoryalgorithm_set.all()
    return render(request, 'scenario_builder/algorithm_dropdown_list_options.html', {'algorithms': algorithms})


def load_parameter_options(request):
    algorithm_id = request.GET.get('algorithm')
    algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
    parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
    context = {
        'parameters': {
            parameter: InventoryAlgorithmParameterValue.objects.filter(parameter=parameter) for parameter in
            parameters}}
    return render(request, 'scenario_builder/parameters_dropdown_list_options.html', context)


class ScenarioResultView(DetailView):
    """
    View that triggers the evaluation of a scenario and displays the results.
    """

    template_name = 'scenario_builder/scenario_evaluation.html'
    model = Scenario
    context_object_name = 'scenario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        layers = Layer.objects.filter(scenario=scenario)
        context['feature_collections'] = {layer.name: layer.get_feature_collection() for layer in layers}
        return context

    # def get(self, request, *args, **kwargs):
    #     super().get(request, *args, **kwargs)
    #     layers = Layer.objects.filter(scenario=self.object)
    #     feature_collections = {layer.name: layer.get_feature_collection() for layer in layers}
    #     return self.render_to_response(self.context)


class ScenarioResultDetailMapView(DetailView):
    """View of an individual result map in large size"""
    model = Layer
    context_object_name = 'layer'
    template_name = 'scenario_builder/result_detail_map.html'

    def get_object(self, **kwargs):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algo_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm)


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

    def get(self, request, *args, **kwargs):
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

    def get(self, request):
        name = request.GET.get('function_name')
        qs = Catchment.objects.filter(name=name)

        serializer = CatchmentSerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
