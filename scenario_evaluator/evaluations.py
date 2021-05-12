from distributions.plots import BarChart, DataSet
from flexibi_dst.exceptions import UnitMismatchError
from flexibi_dst.models import TemporalDistribution
from layer_manager.models import LayerAggregatedDistribution
from material_manager.models import BaseObjects


class ScenarioResult:
    scenario = None
    layers = None
    feedstocks = None
    timesteps = None

    def __init__(self, scenario):
        self.scenario = scenario
        self.layers = scenario.layer_set.all()
        self.feedstocks = scenario.feedstocks()
        self.timesteps = self.homogenize_timesteps()

    def homogenize_timesteps(self):
        layer = self.layers.first()  # TODO: Fix this!!!
        dist = layer.layeraggregateddistribution_set.first().distribution
        return [timestep for timestep in dist.timestep_set.all()]

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

    def total_production(self):
        production_value = 0
        unit = None
        for layer in self.layers:
            agg_value = layer.layeraggregatedvalue_set.get(name='Total production')
            if unit is None:
                unit = agg_value.unit
            if agg_value.unit != unit:
                raise UnitMismatchError
            production_value += agg_value.value
        total_production = DataSet(label='Total production', data={'Total': production_value}, unit=unit)
        return total_production

    def total_production_per_feedstock(self):
        data = {}
        unit = None
        for layer in self.layers:
            agg_value = layer.layeraggregatedvalue_set.get(name='Total production')
            unit = agg_value.unit
            data[layer.feedstock.name] = agg_value.value
        production = DataSet(label='Total production per feedstocks', data=data, unit=unit)
        return production

    def get_charts(self):
        charts = {}

        # Total annual production per feedstock
        production = self.total_production_per_feedstock()
        chart = BarChart(
            id='productionPerFeedstockBarChart',
            title='Total annual production per feedstock',
            unit=production.unit
        )
        chart.add_dataset(production)
        charts.update({
            'productionPerFeedstockBarChart': chart.as_dict()
        })

        # Composition of total production by component group
        try:
            group_settings = self.material_component_groups()
            for group_setting in group_settings:
                xlabels, data = self.material_values_for_plot(group_setting)
                chart_id = group_setting.group.name.replace(' ', '') + 'BarChart'
                charts.update({
                    chart_id: BarChart(
                        id=chart_id,
                        title='Production per component: ' + group_setting.group.name,
                        data=data
                    ).as_dict()
                })
        except:
            pass

        # Seasonal production by component
        chart = BarChart(
            id='seasonalFeedstockBarChart',
            title='Seasonal distribution of feedstocks',
            unit='Mg/a',
            show_legend=True
        )
        for ds in self.seasonal_production_per_component():
            chart.add_dataset(ds)
        charts.update({
            'seasonalFeedstockBarChart': chart.as_dict()
        })

        return charts

    # TODO: Delete when ready
    # def total_production_per_material_component(self):
    #     # This should not depend on the material definition but should be fetched directly from layer. Calculation
    #     # should happen directly in the model algorithm.
    #     total_production_per_feedstock = self.total_production_per_feedstock()
    #     components = {}
    #     for feedstock in self.feedstocks:
    #         for group, content in feedstock.composition().items():
    #             if group not in components:
    #                 components[group] = {}
    #             for share in content['averages']:
    #                 if share.component.name not in components[group]:
    #                     components[group][share.component.name] = 0
    #                 components[group][share.component.name] += share.average * total_production_per_feedstock[
    #                     feedstock]
    #     return components

    def seasonal_production_per_component(self):
        datasets = []
        for layer in self.layers:
            agg_dist = layer.layeraggregateddistribution_set.filter(name='Seasonal production per component')[0]
            for d in agg_dist.serialized:
                d['label'] = f'{layer.feedstock.name}: {d["label"]}'
                datasets.append(DataSet(**d))
        return datasets

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

    def summary_dict(self):
        summary = {
            'scenario': {
                'name': self.scenario.name,
                'description': self.scenario.description
            },
            'timesteps': [{
                'name': timestep.name,
                'composition': {
                    'materials': [{
                        'name': feedstock,
                        'amount': amount,
                        'unit': 'Mg/a'
                    } for feedstock, amount in self.total_production_per_feedstock().items()]
                }
            } for timestep in self.timesteps]
        }
        return summary
