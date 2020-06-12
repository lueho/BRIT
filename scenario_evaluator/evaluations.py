class ScenarioResult:
    scenario = None
    layers = None

    def __init__(self, scenario):
        self.scenario = scenario
        self.layers = []
        for layer in scenario.layer_set.all():
            self.layers.append(layer)

    def layer_summaries(self):
        layer_summaries = {}
        for layer in self.layers:
            layer_summaries[layer] = {
                'feedstock': layer.feedstock(),
                'algorithm': layer.algorithm,
                'aggregated_values': [aggregate for aggregate in layer.layeraggregatedvalue_set.all()],
                'map_link': layer.feature_table_url
            }
        return layer_summaries
