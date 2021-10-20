import io
import json

from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView

from flexibi_dst.views import DualUserListView
from layer_manager.models import Layer
from material_manager.models import MaterialSettings
from scenario_builder.models import InventoryAlgorithm, Scenario
from scenario_evaluator.evaluations import ScenarioResult
from scenario_evaluator.models import RunningTask
from users.models import ReferenceUsers


class ScenarioListView(DualUserListView):
    model = Scenario
    template_name = 'scenario_list.html'


class ScenarioResultView(DetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = 'scenario_result_detail.html'
    model = Scenario
    context_object_name = 'scenario'
    object = None
    allow_edit = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        result = ScenarioResult(scenario)
        context['layers'] = [layer.as_dict() for layer in result.layers]
        context['charts'] = result.get_charts()
        context['allow_edit'] = self.allow_edit
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

    def test_func(self):
        self.object = self.get_object()
        standard_owner = ReferenceUsers.objects.get.standard_owner
        if self.object.owner == standard_owner:
            if self.request.user == standard_owner:
                self.allow_edit = True
            return True
        elif self.object.owner == self.request.user:
            self.allow_edit = True
            return True
        else:
            return False


class ScenarioEvaluationProgressView(DetailView):
    """
    The page users land on if a scenario is being calculated. The progress of the evaluation is shown and upon
    finishing the calculation, the user is redirected to the result page.
    """

    template_name = 'evaluation_progress.html'
    model = Scenario


class ScenarioResultDetailMapView(DetailView):
    """View of an individual result map in large size"""
    model = Layer
    context_object_name = 'layer'
    template_name = 'result_detail_map.html'

    def get_object(self, **kwargs):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        feedstock = MaterialSettings.objects.get(id=self.kwargs.get('feedstock_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm, feedstock=feedstock)


def download_scenario_result_summary(request, scenario_pk):
    scenario = Scenario.objects.get(id=scenario_pk)
    result = ScenarioResult(scenario)
    with io.StringIO(json.dumps(result.summary_dict(), indent=4)) as file:
        response = HttpResponse(file, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=scenario_{scenario_pk}_result_summary.json'
        return response
