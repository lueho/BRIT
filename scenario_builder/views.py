from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView, DeleteView, DetailView, ListView
from django.views.generic.detail import SingleObjectMixin
from rest_framework.views import APIView

from .forms import CatchmentForm
from .models import Catchment, Scenario, ScenarioInventoryConfiguration
from .scenarios import GisInventory
from .serializers import CatchmentSerializer


class InventoryMixin(SingleObjectMixin):
    """
    A mixin that provides functionality for performing flexibi bioresource inventories
    """
    inventory_config = None
    inventory_result = None
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
                parameter_list.append({'name': parameter,
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
        self.inventory_config = self.get_inventory_config(self.object)
        self.inventory_config_list = self.reformat_inventory_config(self.inventory_config)
        context = self.get_context_data(object=self.object)
        context['config'] = self.inventory_config_list
        return self.render_to_response(context)


class ScenarioResultView(InventoryMixin, DetailView):
    """
    View that triggers the evaluation of a scenario and displays the results.
    """

    model = Scenario
    template_name = 'scenario_builder/scenario_output.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        inventory = GisInventory(self.object)
        inventory.run()
        context = self.get_context_data(object=self.object)
        context['inventory_result'] = inventory.results_as_list()
        return self.render_to_response(context)


class ScenarioListView(ListView):
    queryset = Scenario.objects.all()


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


class CatchmentAPIView(APIView):

    def get(self, request):
        name = request.GET.get('name')
        qs = Catchment.objects.filter(name=name)

        serializer = CatchmentSerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
