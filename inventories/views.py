import io
import json

from celery.result import AsyncResult
from dal_select2.views import Select2ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, View
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import ModelFormMixin
from rest_framework.views import APIView

from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset
from maps.serializers import BaseResultMapSerializer
from maps.views import MapMixin
from materials.models import SampleSeries
from utils.views import (OwnedObjectCreateView, OwnedObjectModalDeleteView, PublishedObjectFilterView,
                         UserCreatedObjectDetailView, UserCreatedObjectUpdateView, UserOwnedObjectFilterView)
from .evaluations import ScenarioResult
from .filters import ScenarioFilterSet
from .forms import (ScenarioInventoryConfigurationAddForm, ScenarioInventoryConfigurationUpdateForm,
                    ScenarioModelForm, SeasonalDistributionModelForm)
from .models import (InventoryAlgorithm, InventoryAlgorithmParameter, InventoryAlgorithmParameterValue, RunningTask,
                     Scenario, ScenarioInventoryConfiguration, ScenarioStatus)
from .tasks import run_inventory


class SeasonalDistributionCreateView(LoginRequiredMixin, CreateView):
    form_class = SeasonalDistributionModelForm
    template_name = 'seasonal_distribution_create.html'
    success_url = '/inventories/materials/{material_id}'


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioNameAutocompleteView(Select2ListView):

    def get_list(self):
        if self.request.user.is_authenticated:
            qs = Scenario.objects.accessible_by_user(self.request.user)
        else:
            qs = Scenario.objects.published()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs.values_list('name', flat=True)


class PublishedScenarioFilterView(PublishedObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet


class UserOwnedScenarioFilterView(UserOwnedObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet


class ScenarioCreateView(LoginRequiredMixin, OwnedObjectCreateView):
    form_class = ScenarioModelForm
    permission_required = set()


class ScenarioDetailView(MapMixin, UserCreatedObjectDetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    object = None
    config = None
    allow_edit = False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context['config'] = self.config
        context['allow_edit'] = self.allow_edit
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        run_inventory(scenario.id)
        return redirect('scenario-result', scenario.id)


class ScenarioUpdateView(UserCreatedObjectUpdateView):
    model = Scenario
    form_class = ScenarioModelForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'region_id': self.object.region.id})
        return kwargs


class ScenarioModalDeleteView(OwnedObjectModalDeleteView):
    model = Scenario
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('scenario-list')
    permission_required = 'inventories.delete_scenario'


def get_evaluation_status(request, task_id=None):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result,
        "task_info": task_result.info
    }
    return JsonResponse(result, status=200)


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
        feedstock = SampleSeries.objects.get(id=request.POST.get('feedstock'))
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
        return redirect('scenario-detail', pk=scenario_id)

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
        feedstock = SampleSeries.objects.get(id=request.POST.get('feedstock'))
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
        return redirect('scenario-detail', pk=request.POST.get('scenario'))

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
        self.feedstock = SampleSeries.objects.get(id=self.kwargs.get('feedstock_pk'))
        self.scenario.remove_inventory_algorithm(algorithm=self.algorithm, feedstock=self.feedstock)
        return redirect('scenario-detail', pk=self.scenario.id)


def download_scenario_summary(request, scenario_pk):
    file_name = f'scenario_{scenario_pk}_summary.json'
    scenario = Scenario.objects.get(id=scenario_pk)
    with io.StringIO(json.dumps(scenario.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=%s' % file_name
        return response


def load_catchment_options(request):
    region_id = request.GET.get('region_id') or request.GET.get('region')
    if region_id:
        return render(request, 'catchment_dropdown_list_options.html',
                      {'catchments': Catchment.objects.filter(parent_region_id=region_id)})
    else:
        return render(request, 'catchment_dropdown_list_options.html', {'catchments': Catchment.objects.none()})


def load_geodataset_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock'):
        feedstock = SampleSeries.objects.get(id=request.GET.get('feedstock'))
        if request.GET.get('options') == 'create':
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock.material)
        elif request.GET.get('options') == 'update':
            current = GeoDataset.objects.filter(id=request.GET.get('current_geodataset'))
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock.material).union(current)
        else:
            geodatasets = scenario.available_geodatasets()
    else:
        geodatasets = GeoDataset.objects.none()
    return render(request, 'geodataset_dropdown_list_options.html', {'geodatasets': geodatasets})


def load_algorithm_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock') and request.GET.get('geodataset'):
        feedstock = SampleSeries.objects.get(id=request.GET.get('feedstock'))
        geodataset = GeoDataset.objects.get(id=request.GET.get('geodataset'))
        if request.GET.get('options') == 'create':
            algorithms = scenario.remaining_inventory_algorithm_options(feedstock, geodataset)
        elif request.GET.get('options') == 'update':
            current_algorithm = InventoryAlgorithm.objects.filter(id=request.GET.get('current_inventory_algorithm'),
                                                                  feedstock=feedstock.material, geodataset=geodataset)
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
            'catchment_id': layer.scenario.catchment_id,
            'region_id': layer.scenario.region_id,
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)


class ScenarioResultView(MapMixin, UserCreatedObjectDetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = 'scenario_result_detail.html'
    model = Scenario

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        result = ScenarioResult(scenario)
        context['layers'] = [layer.as_dict() for layer in result.layers]
        context['charts'] = result.get_charts()
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        if scenario.status == 2:
            context = {
                'scenario': scenario,
                'task_list': {'tasks': []}
            }
            for task in RunningTask.objects.filter(scenario=scenario):
                context['task_list']['tasks'].append({
                    'task_id': task.uuid,
                    'algorithm_name': task.algorithm.name
                })

            return render(request, 'evaluation_progress.html', context)
        else:
            context = self.get_context_data()
            return self.render_to_response(context)


class ScenarioEvaluationProgressView(DetailView):
    """
    The page users land on if a scenario is being calculated. The progress of the evaluation is shown and upon
    finishing the calculation, the user is redirected to the result page.
    """

    template_name = 'evaluation_progress.html'
    model = Scenario


class ScenarioResultDetailMapView(MapMixin, DetailView):
    """View of an individual result map in large size"""
    model = Layer
    context_object_name = 'layer'
    template_name = 'result_detail_map.html'

    def get_object(self, **kwargs):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        feedstock = SampleSeries.objects.get(id=self.kwargs.get('feedstock_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm, feedstock=feedstock)

    def get_region_feature_id(self):
        return self.object.algorithm.geodataset.region.id

    def get_catchment_feature_id(self):
        return self.object.scenario.catchment.id

    def get_map_title(self):
        return f'{self.object.scenario.name}: {self.object.algorithm.geodataset.name}'


def download_scenario_result_summary(request, scenario_pk):
    scenario = Scenario.objects.get(id=scenario_pk)
    result = ScenarioResult(scenario)
    with io.StringIO(json.dumps(result.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=scenario_{scenario_pk}_result_summary.json'
        return response
