class ScenarioResult:
    scenario = None
    layers = None

    def __init__(self, scenario):
        self.scenario = scenario
        self.layers = []
        for layer in scenario.layer_set.all():
            self.layers.append(layer)

    def production_values_for_plot(self):
        labels, values = [], []
        for label, value in self.total_production_per_feedstock().items():
            labels.append(label)
            values.append(value)
        return labels, values

    def total_annual_production(self):
        total_production = 0
        for layer in self.layers:
            layer_production_agg = layer.layeraggregatedvalue_set.get(name='Total production')
            total_production += layer_production_agg.value
        return total_production

    def total_production_per_feedstock(self):
        production = {}
        for layer in self.layers:
            feedstock = layer.algorithm.feedstock.name
            if feedstock not in production.keys():
                production[feedstock] = 0
            production[feedstock] += layer.layeraggregatedvalue_set.get(name='Total production').value
        return production

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
