from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
from distributions.models import TemporalDistribution
from distributions.plots import Distribution
from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import Scenario
from materials.models import MaterialComponentGroup, SampleSeries


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def hamburg_park_production(cls, **kwargs):
        keep_columns = ['anlagenname', 'belegenheit', 'gruenart', 'nutzcode']

        kwargs.update({'source_model': HamburgGreenAreas})
        kwargs.update({'keep_columns': keep_columns})
        return super().avg_area_yield(**kwargs)

    @classmethod
    def hamburg_roadside_tree_production(cls, **kwargs):
        if not any(key in kwargs for key in ['scenario_id', 'catchment_id']):
            raise ValueError('Either a scenario_id or catchment_id must be provided.')
        if 'scenario_id' in kwargs and 'catchment_id' in kwargs:
            if Scenario.objects.get(id=kwargs.get('scenario_id')).catchment_id != kwargs.get('catchment_id'):
                raise ValueError('The provided scenario_id does not match the provided catchment_id.')
        if 'scenario_id' in kwargs:
            kwargs.update({'catchment_id': Scenario.objects.get(id=kwargs.get('scenario_id')).catchment_id})
        kwargs.update({'source_model': HamburgRoadsideTrees})
        result = super().avg_point_yield(**kwargs)

        scenario = Scenario.objects.get(id=kwargs.get('scenario_id'))
        feedstock = SampleSeries.objects.get(id=kwargs.get('feedstock_id'))

        result['aggregated_distributions'] = []

        temporal_distribution = TemporalDistribution.objects.get(name='Summer/Winter')

        # Create the distribution for the stacked barchart seasonal production per component
        group = MaterialComponentGroup.objects.get(name='Macro Components')
        distribution = Distribution(
            temporal_distribution,
            name='Seasonal production per component'
        )

        for agg_val in result['aggregated_values']:
            if agg_val['name'] == 'Total production':
                total_production = agg_val['value']
        inv_shares = feedstock.inventoryamountshare_set.filter(scenario=scenario)
        if inv_shares.exists():
            temp_dist = {timestep: inv_shares.get(timestep=timestep).average for timestep in temporal_distribution.timestep_set.all()}
            for share in feedstock.shares:
                if share.composition.group == group:
                    if share.timestep.distribution == temporal_distribution:
                        value = share.average * temp_dist[share.timestep] * total_production
                        distribution.add_share(share.timestep, share.component, value)
            if distribution.serialize()['sets']:
                result['aggregated_distributions'].append(distribution.serialize())

        return result
