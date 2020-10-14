from scenario_builder.models import Material


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

    def material_values_for_plot(self, group):
        labels, values = [], []
        for label, value in self.total_material_components()[group].items():
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
            feedstock = layer.feedstock.name
            if feedstock not in production.keys():
                production[feedstock] = 0
            production[feedstock] += layer.layeraggregatedvalue_set.get(name='Total production').value
        return production

    def total_material_components(self):
        total_production_per_feedstock = self.total_production_per_feedstock()
        components = {}
        for feedstock in total_production_per_feedstock:
            material = Material.objects.get(name=feedstock)
            for group_name, group_content in material.grouped_components().items():
                if group_name not in components:
                    components[group_name] = {}
                for component in group_content:
                    if component.name not in components[group_name]:
                        components[group_name][component.name] = 0
                    components[group_name][component.name] += component.average * total_production_per_feedstock[
                        feedstock]
        return components

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
