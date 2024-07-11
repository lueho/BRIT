import io
import json

from celery.result import AsyncResult
from dal_select2.views import Select2QuerySetView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, DetailView
from extra_views import UpdateWithInlinesView
from rest_framework import viewsets
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from layer_manager.models import Layer
from maps.serializers import BaseResultMapSerializer
from maps.views import MapMixin
from materials.models import SampleSeries
from utils.views import (OwnedObjectCreateView, OwnedObjectDetailView, OwnedObjectModalDeleteView,
                         OwnedObjectUpdateView, PublishedObjectFilterView, RestrictedOwnedObjectDetailView,
                         UserOwnedObjectFilterView, ModelPermissionOrOwnerMixin,
                         PermissionOrOwnerOrPublishedMixin)
from utils.viewsets import AutoPermModelViewSet
from .evaluations import ScenarioResult
from .filters import ScenarioFilterSet
from .forms import (ScenarioModelForm, SeasonalDistributionModelForm, ScenarioConfigurationModelForm,
                    ScenarioParameterSettingInline, NoFormTagFormSetHelper)
from .models import (Algorithm, ParameterValue, RunningTask,
                     Scenario, ScenarioConfiguration, ScenarioStatus)
from .tasks import run_inventory


class SeasonalDistributionCreateView(LoginRequiredMixin, CreateView):
    form_class = SeasonalDistributionModelForm
    template_name = 'seasonal_distribution_create.html'
    success_url = '/inventories/materials/{material_id}'


class AlgorithmNameAutocompleteView(Select2QuerySetView):

    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = Algorithm.objects.accessible_by_user(self.request.user)
        else:
            qs = Algorithm.objects.published()

        geodataset_id = self.forwarded.get('geodataset', None)
        if geodataset_id:
            qs = qs.filter(geodataset_id=geodataset_id)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs.order_by('name')


class ParameterValueNameAutocompleteView(Select2QuerySetView):

    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = ParameterValue.objects.accessible_by_user(self.request.user)
        else:
            qs = ParameterValue.objects.published()

        parameter_id = self.forwarded.get('parameter', None)
        if parameter_id:
            qs = qs.filter(parameter_id=parameter_id)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs.order_by('name')


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedScenarioFilterView(PublishedObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet
    permission_required = set()


class UserOwnedScenarioFilterView(UserOwnedObjectFilterView):
    model = Scenario
    filterset_class = ScenarioFilterSet


class ScenarioCreateView(LoginRequiredMixin, OwnedObjectCreateView):
    form_class = ScenarioModelForm
    permission_required = set()


# There is not ScenarioDetailView. Use ScenarioConfigurationDetailView instead.


class ScenarioUpdateView(OwnedObjectUpdateView):
    model = Scenario
    form_class = ScenarioModelForm
    permission_required = 'inventories.change_scenario'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'region_id': self.object.region.id})
        return kwargs


class ScenarioModalDeleteView(OwnedObjectModalDeleteView):
    model = Scenario
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('scenario-list')
    permission_required = 'inventories.delete_scenario'


# ----------- Scenario utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioNameAutocompleteView(Select2QuerySetView):

    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = Scenario.objects.accessible_by_user(self.request.user)
        else:
            qs = Scenario.objects.published()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs.order_by('name')


def download_scenario_summary(request, scenario_pk):
    file_name = f'scenario_{scenario_pk}_summary.json'
    scenario = Scenario.objects.get(id=scenario_pk)
    with io.StringIO(json.dumps(scenario.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=%s' % file_name
        return response


# ----------- Scenario configuration -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioConfigurationCreateView(LoginRequiredMixin, OwnedObjectCreateView):
    """
    This view is responsible for creating a new ScenarioConfiguration instance.
    During the creation initially only the feedstock, dataset and algorithm are selected. For simplicity, the values
    of the parameters for the algorithm are set to their defaults. This can later be changed by the user through the
    ScenarioConfigurationUpdateView, which includes inline forms for all parameters that belong to the selected
    algorithm. This requires that the workflow only allows creating and removing actual ScenarioConfiguration objects.
    Once created, scenario, feedstock, dataset and algorithm cannot be changed. Updates can only be done by altering
    the parameter values of the ScenarioParameterSetting objects.
    """

    model = ScenarioConfiguration
    form_class = ScenarioConfigurationModelForm
    permission_required = set()

    def get_initial(self):
        return {'scenario': Scenario.objects.get(id=self.kwargs.get('pk'))}


class ScenarioConfigurationDetailView(PermissionOrOwnerOrPublishedMixin, MapMixin, OwnedObjectDetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    object = None
    permission_required = ['inventories.view_scenario', 'inventories.view_scenarioconfiguration']
    config = None

    load_region = True
    region_url = reverse_lazy('data.region-geometries')
    region_layer_style = {
        "color": "#A1221C",
        "fillOpacity": 0.0
    }

    load_catchment = True
    catchment_url = reverse_lazy('data.catchment-geometries')
    catchment_layer_style = {
        'color': '#4061d2',
    }

    load_features = False
    adjust_bounds_to_features = False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # If the scenario has failed, delete all registered tasks
        if self.object.status == 4:
            RunningTask.objects.filter(scenario=self.object).delete()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context['config'] = self.config
        return self.render_to_response(context)

    def get_catchment_id(self):
        return self.object.catchment.id

    def get_region_id(self):
        return self.object.region.id

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        run_inventory.delay(scenario.id)
        return redirect('scenario-result', scenario.id)


class ScenarioConfigurationUpdateView(ModelPermissionOrOwnerMixin, UpdateWithInlinesView):
    """
    This view is responsible for updating a ScenarioConfiguration instance. Note that the fields of the actual
    ScenarioConfiguration object are locked, once created. Updates in this view are done by altering the parameter
    values of the ScenarioParameterSetting objects that belong to the selected algorithm. To change the scenario,
    feedstock, dataset or algorithm, a new ScenarioConfiguration object has to be created.
    """

    model = ScenarioConfiguration
    form_class = ScenarioConfigurationModelForm
    inlines = [ScenarioParameterSettingInline]
    template_name = 'configure_algorithm.html'
    formset_helper_class = NoFormTagFormSetHelper
    permission_required = 'inventories.change_scenarioconfiguration'

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        kwargs.update({'formset_helper': self.formset_helper_class})
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()


class ScenarioInventoryConfigurationModalDeleteView(OwnedObjectModalDeleteView):
    """
    This view handles the deletion of a ScenarioConfiguration instance. It inherits from OwnedObjectModalDeleteView,
    which is a custom view designed to handle deletion of objects owned by a user.
    """

    model = ScenarioConfiguration
    success_message = 'Successfully deleted.'
    permission_required = ['inventories.delete_scenarioconfiguration']

    def get_success_url(self):
        return self.object.scenario.get_absolute_url()


class LayerIsPublishedPermission(BasePermission):

    def has_permission(self, request, view):
        # The OPTIONS method is not associated with any action and should always be allowed
        if request.method in ('OPTIONS', 'HEAD'):
            return True

        layer = Layer.objects.get(table_name=view.kwargs['layer_name'])
        if view.action == 'retrieve' and layer.scenario.publication_status == 'published':
            return True
        return request.user and request.user.is_authenticated


class ResultMapAPI(ReadOnlyModelViewSet):

    queryset = Layer.objects.all()
    permission_classes = [LayerIsPublishedPermission]

    def retrieve(self, request, *args, **kwargs):
        try:
            layer = Layer.objects.get(table_name=kwargs['layer_name'])
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

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


class ScenarioResultView(MapMixin, OwnedObjectDetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = 'scenario_result_detail.html'
    model = Scenario
    object = None
    permission_required = set()
    context_object_name = 'scenario'

    load_region = True
    region_url = reverse_lazy('data.region-geometries')
    region_layer_style = {
        "color": "#A1221C",
        "fillOpacity": 0.0
    }

    load_catchment = True
    catchment_url = reverse_lazy('data.catchment-geometries')
    catchment_layer_style = {
        'color': '#4061d2',
    }

    load_features = False
    adjust_bounds_to_features = False

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

    def get_catchment_id(self):
        return self.object.catchment.id

    def get_region_id(self):
        return self.object.region.id


class ScenarioEvaluationProgressView(DetailView):
    """
    The page users land on if a scenario is being calculated. The progress of the evaluation is shown and upon
    finishing the calculation, the user is redirected to the result page.
    """

    template_name = 'evaluation_progress.html'
    model = Scenario


def get_evaluation_status(request, task_id=None):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        if task_result.successful():
            result = {
                'task_id': task_id,
                'task_status': task_result.status,
                'task_result': task_result.result,
                'task_info': task_result.info
            }
        else:
            result = {
                'task_id': task_id,
                'task_status': task_result.status,
                'task_result': 'The task failed.',
                'task_info': 'The task failed.'
            }
    else:
        result = {
            'task_id': task_id,
            'task_status': task_result.status,
            'task_result': task_result.result,
            'task_info': task_result.info
        }
    return JsonResponse(result, status=200)


class ScenarioResultDetailMapView(MapMixin, DetailView):
    """View of an individual result map in large size"""
    model = Layer
    context_object_name = 'layer'
    template_name = 'result_detail_map.html'
    region_url = reverse_lazy('data.region-geometries')
    catchment_url = reverse_lazy('data.catchment-geometries')
    catchment_layer_style = {
        'color': '#04555E',
        'fillOpacity': 0.1,
        'weight': 1
    }
    feature_layer_style = {
        'color': '#63c36c',
        'fillOpacity': 1,
        'radius': 5,
        'stroke': False
    }

    def get_object(self, **kwargs):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        algorithm = Algorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        feedstock = SampleSeries.objects.get(id=self.kwargs.get('feedstock_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm, feedstock=feedstock)

    def get_map_title(self):
        return "Result Map"

    def get_region_id(self):
        return self.object.scenario.region.id

    def get_catchment_id(self):
        return self.object.scenario.catchment.id

    def get_feature_url(self):
        return reverse('data.result_layer', args=[self.object.table_name])


def download_scenario_result_summary(request, scenario_pk):
    scenario = Scenario.objects.get(id=scenario_pk)
    result = ScenarioResult(scenario)
    with io.StringIO(json.dumps(result.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=scenario_{scenario_pk}_result_summary.json'
        return response
