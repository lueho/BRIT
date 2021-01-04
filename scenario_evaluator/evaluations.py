from scenario_builder.models import Material


class ScenarioResult:
    scenario = None
    layers = None

    def __init__(self, scenario):
        self.scenario = scenario
        self.layers = []
        for layer in scenario.layer_set.all():
            self.layers.append(layer)

    def material_component_groups(self):
        materials = self.scenario.feedstocks()
        return set([group for material in materials for group in material.component_groups(scenario=self.scenario)])

    def get_plot_data(self):
        plot_data = {}

        # Total annual production per feedstock
        xlabels, data = self.production_values_for_plot()
        plot_data['productionPerFeedstockBarChart'] = {}
        plot_data['productionPerFeedstockBarChart']['chart_name'] = 'Total annual production per feedstock'
        plot_data['productionPerFeedstockBarChart']['chart_type'] = 'stacked_barchart'
        plot_data['productionPerFeedstockBarChart']['dataset'] = {'labels': xlabels, 'values': data}
        plot_data['productionPerFeedstockBarChart']['unit'] = 'Mg/a'
        plot_data['productionPerFeedstockBarChart']['show_legend'] = False

        # Composition of total production by component group
        groups = self.material_component_groups()
        for group in groups:
            xlabels, data = self.material_values_for_plot(group)
            chart_id = group.name.replace(' ', '') + 'BarChart'
            plot_data[chart_id] = {}
            plot_data[chart_id]['chart_name'] = 'Production per component: ' + group.name
            plot_data[chart_id]['chart_type'] = 'stacked_barchart'
            plot_data[chart_id]['dataset'] = {'labels': xlabels, 'values': data}
            plot_data[chart_id]['unit'] = 'Mg/a'
            plot_data[chart_id]['show_legend'] = False

        # Seasonal distribution of total production
        xlabels, data = self.seasonal_production_values_for_plot()
        plot_data['seasonalFeedstockBarChart'] = {}
        plot_data['seasonalFeedstockBarChart']['chart_name'] = 'Seasonal distribution of feedstocks'
        plot_data['seasonalFeedstockBarChart']['chart_type'] = 'stacked_barchart'
        plot_data['seasonalFeedstockBarChart']['dataset'] = {'labels': xlabels, 'values': data}
        plot_data['seasonalFeedstockBarChart']['unit'] = 'Mg'
        plot_data['seasonalFeedstockBarChart']['show_legend'] = True

        return plot_data

    def production_values_for_plot(self):
        xlabels = []
        data = [{
            'label': 'Total',
            'data': []
        }]
        for label, value in self.total_production_per_feedstock().items():
            xlabels.append(label)
            data[0]['data'].append(value)
        return xlabels, data

    def material_values_for_plot(self, group):
        xlabels = []
        data = [{
            'label': 'Total',
            'data': []
        }]
        for label, value in self.total_material_components()[group].items():
            xlabels.append(label)
            data[0]['data'].append(value)
        return xlabels, data

    def seasonal_production_values_for_plot(self):
        xlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        data = []
        for layer in self.layers:
            for distribution in layer.layeraggregateddistribution_set.filter(type='seasonal'):
                data.append({
                    'label': distribution.name,
                    'data': distribution.distribution
                })
        return xlabels, data

    def total_annual_production(self):
        total_production = 0
        for layer in self.layers:
            layer_production_agg = layer.layeraggregatedvalue_set.get(name='Total production')
            total_production += layer_production_agg.value
        return total_production / 1000

    def total_production_per_feedstock(self):
        production = {}
        for layer in self.layers:
            feedstock = layer.feedstock.name
            if feedstock not in production.keys():
                production[feedstock] = 0
            production[feedstock] += layer.layeraggregatedvalue_set.get(name='Total production').value / 1000
        return production

    def seasonal_production_per_feedstock(self):
        pass

    def total_material_components(self):
        total_production_per_feedstock = self.total_production_per_feedstock()
        components = {}
        for feedstock in total_production_per_feedstock.keys():
            material = Material.objects.get(name=feedstock)
            for group, content in material.grouped_component_shares(scenario=self.scenario).items():
                if group not in components:
                    components[group] = {}
                for share in content['shares']:
                    if share.component.name not in components[group]:
                        components[group][share.component.name] = 0
                    components[group][share.component.name] += share.average * total_production_per_feedstock[
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
