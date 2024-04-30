from distributions.models import TemporalDistribution
from distributions.plots import BarChart, DataSet
from layer_manager.models import LayerAggregatedDistribution
from utils.exceptions import UnitMismatchError


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
        try:
            layer = self.layers.first()  # TODO: Fix this!!!
            dist = layer.layeraggregateddistribution_set.first().distribution
            return [timestep for timestep in dist.timestep_set.all()]
        except AttributeError:
            return []

    def material_component_groups(self):
        groups = []
        sample_series = self.scenario.feedstocks()
        for series in sample_series.all():
            for sample in series.samples.all():
                for composition in sample.compositions.all():
                    groups.append(composition.group)
        return list(set(groups))

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
        production = DataSet(label='Total production per feedstock', data=data, unit=unit)
        return production

    def total_production_per_component(self):
        data = {}
        total_production_per_feedstock = self.total_production_per_feedstock().__dict__
        for sample_series in self.scenario.feedstocks():
            data[sample_series.name] = {}
            total_production = total_production_per_feedstock['data'][sample_series.name]
            for sample in sample_series.samples.all():
                for composition in sample.compositions.all():
                    data[sample_series.name][composition.group.name] = {}
                    for share in composition.shares.all():
                        data[sample_series.name][composition.group.name][
                            share.component.name] = share.average * total_production
        return data

    def seasonal_production_per_component(self):
        datasets = []
        for layer in self.layers:
            agg_dist = layer.layeraggregateddistribution_set.filter(name='Seasonal production per component')[0]
            for d in agg_dist.serialized:
                d['label'] = f'{layer.feedstock.name}: {d["label"]}'
                datasets.append(DataSet(**d))
        return datasets

    def get_charts(self):
        charts = {}

        # Total annual production per feedstock
        try:
            chart_id = 'productionPerFeedstockBarChart'
            production = self.total_production_per_feedstock()
            chart = BarChart(
                id=chart_id,
                title='Total annual production per feedstock',
                unit=production.unit
            )
            chart.add_dataset(production)
            charts.update({chart_id: chart.as_old_dict()})
        except:
            pass

        # Seasonal production by component
        try:
            chart_id = 'seasonalFeedstockBarChart'
            chart = BarChart(
                id=chart_id,
                title='Seasonal distribution of feedstocks',
                unit='Mg/a',
                show_legend=True
            )
            for ds in self.seasonal_production_per_component():
                chart.add_dataset(ds)
            charts.update({chart_id: chart.as_old_dict()})
        except:
            pass

        # Composition of total production by component group
        try:
            sample_series = self.scenario.feedstocks()
            for series in sample_series.all():
                for sample in series.samples.all():
                    for composition in sample.compositions.all():
                        chart_id = f"{series.name.replace(' ', '')}{composition.group.name.replace(' ', '')}BarChart"
                        chart = BarChart(
                            id=chart_id,
                            title='Production per component: ' + composition.group.name,
                            unit='Mg/a',
                            show_legend=True
                        )
                        data = self.total_production_per_component()[series.name][composition.group.name]
                        if sum(data.values()) > 0:
                            chart.add_dataset(DataSet(label=f'{series.name}: Total', data=data, unit='Mg/a'))
                            charts.update({chart_id: chart.as_old_dict()})
        except:
            pass

        return charts

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
