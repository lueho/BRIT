from flexibi_dst.models import TemporalDistribution
from layer_manager.models import LayerAggregatedDistribution
from material_manager.models import BaseObjects


class Plot:
    name = None
    chart_id = None
    chart_type = None
    dataset = None
    unit = None
    show_legend = None

    def __init__(self, chart_id='newPlot', name='New Plot', dataset=None, chart_type='stacked_barchart', unit='Mg/a',
                 show_legend=False):
        self.name = name
        self.chart_id = chart_id
        self.chart_type = chart_type
        self.unit = unit
        self.show_legend = show_legend
        self.dataset = {} if not dataset else dataset

    @property
    def serialized(self):
        return {
            self.chart_id: {
                'chart_name': self.name,
                'chart_type': self.chart_type,
                'unit': self.unit,
                'show_legend': self.show_legend,
                'dataset': self.dataset
            }
        }

    @property
    def labels(self):
        return self.dataset['labels']

    @labels.setter
    def labels(self, labels):
        self.dataset['labels'] = labels

    @property
    def values(self):
        return self.dataset['values']

    @values.setter
    def values(self, values):
        self.dataset['values'] = values


class ScenarioResult:
    scenario = None
    layers = None

    def __init__(self, scenario):
        self.scenario = scenario
        self.layers = scenario.layer_set.all()

    def material_component_groups(self):
        group_settings = []
        material_settings = self.scenario.feedstocks()
        for material_setting in material_settings:
            for group_setting in material_setting.materialcomponentgroupsettings_set.all():
                if not group_setting.group == BaseObjects.objects.get.base_group:
                    group_settings.append(group_setting)
        return list(set(group_settings))

    def distributions(self):
        return TemporalDistribution.objects.filter(id__in=[ad['distribution'] for ad in
                                                           LayerAggregatedDistribution.objects.filter(
                                                               layer__in=self.layers).values(
                                                               'distribution').distinct()])

    def get_plot_data(self):
        plot_data = {}

        # Total annual production per feedstock
        xlabels, data = self.production_values_for_plot()
        plot = Plot(
            chart_id='productionPerFeedstockBarChart',
            name='Total annual production per feedstock',
            dataset={'labels': xlabels, 'values': data}
        )
        plot_data.update(plot.serialized)

        # Composition of total production by component group
        group_settings = self.material_component_groups()
        for group_setting in group_settings:
            xlabels, data = self.material_values_for_plot(group_setting)
            chart_id = group_setting.group.name.replace(' ', '') + 'BarChart'
            plot = Plot(
                chart_id=chart_id,
                name='Production per component: ' + group_setting.group.name,
                dataset={'labels': xlabels, 'values': data}
            )
            plot_data.update(plot.serialized)

        # Seasonal distribution of total production
        xlabels, data = self.seasonal_production_for_plot()
        plot = Plot(
            chart_id='seasonalFeedstockBarChart',
            name='Seasonal distribution of feedstocks',
            dataset={'labels': xlabels, 'values': data[0]},  # TODO: allow several distributions
            show_legend=True
        )
        plot_data.update(plot.serialized)

        return plot_data

    def production_values_for_plot(self):
        xlabels = []
        data = [{
            'label': 'Total',
            'data': []
        }]
        for material_settings, value in self.total_production_per_feedstock().items():
            xlabels.append(material_settings.material.name)
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

    def seasonal_production_for_plot(self):
        distribution = TemporalDistribution.objects.get(name='Months of the year')  # FIXME: allow more than one distribution
        xlabels = [timestep.name for timestep in distribution.timestep_set.all()]
        data = []
        for layer in self.layers:
            for aggdist in layer.layeraggregateddistribution_set.filter(distribution=distribution):
                data.append(aggdist.serialized)
        print(data)
        return xlabels, data

    def total_annual_production(self):
        total_production = 0
        for layer in self.layers:
            layer_production_agg = layer.layeraggregatedvalue_set.get(name='Total annual production')
            total_production += layer_production_agg.value
        return total_production / 1000

    def total_production_per_feedstock(self):
        production = {}
        for layer in self.layers:
            feedstock = layer.feedstock
            if feedstock not in production.keys():
                production[feedstock] = 0
            production[feedstock] += layer.layeraggregatedvalue_set.get(name='Total annual production').value / 1000
        return production

    def seasonal_production_per_feedstock(self):
        pass

    def total_material_components(self):
        total_production_per_feedstock = self.total_production_per_feedstock()
        components = {}
        for feedstock in total_production_per_feedstock.keys():
            for group, content in feedstock.composition().items():
                if group not in components:
                    components[group] = {}
                for share in content['averages']:
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
