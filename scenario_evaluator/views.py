from django.views.generic import DetailView

from layer_manager.models import Layer
from scenario_builder.models import InventoryAlgorithm, Scenario


class ScenarioResultView(DetailView):
    """
    View with summaries of the results of each algorithm and a total summary.
    """

    template_name = 'scenario_builder/scenario_evaluation.html'
    model = Scenario
    context_object_name = 'scenario'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenario = self.object
        layers = Layer.objects.filter(scenario=scenario)
        context['feature_collections'] = {layer.name: layer.get_feature_collection() for layer in layers}
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
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algo_pk'))
        return Layer.objects.get(scenario=scenario, algorithm=algorithm)
