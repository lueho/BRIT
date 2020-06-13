from django.views.generic import DetailView, ListView

from layer_manager.models import Layer
from scenario_builder.models import InventoryAlgorithm, Scenario
from scenario_evaluator.evaluations import ScenarioResult


class ScenarioListView(ListView):
    model = Scenario
    template_name = 'scenario_evaluator/scenario_list.html'


class ScenarioResultView(DetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = 'scenario_evaluator/scenario_result_detail.html'
    model = Scenario
    context_object_name = 'scenario'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        result = ScenarioResult(scenario)
        context['layers'] = [layer.as_dict() for layer in Layer.objects.filter(scenario=scenario)]
        labels, values = result.production_values_for_plot()
        context['plotdata'] = {'labels': labels, 'values': values}
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data()
        return self.render_to_response(context)


class ScenarioResultDetailMapView(DetailView):
    """View of an individual result map in large size"""
    model = Layer
    context_object_name = 'layer'
    template_name = 'scenario_builder/result_detail_map.html'

    def get_object(self, **kwargs):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm)
