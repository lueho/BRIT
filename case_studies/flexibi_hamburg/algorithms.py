from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
from distributions.plots import Distribution
from flexibi_dst.models import TemporalDistribution
from materials.models import MaterialComponentGroup, MaterialSettings
from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import Scenario


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def hamburg_park_production(cls, **kwargs):
        keep_columns = ['anlagenname', 'belegenheit', 'gruenart', 'nutzcode']

        kwargs.update({'source_model': HamburgGreenAreas})
        kwargs.update({'keep_columns': keep_columns})
        return super().avg_area_yield(**kwargs)

    @classmethod
    def hamburg_roadside_tree_production(cls, **kwargs):
        kwargs.update({'source_model': HamburgRoadsideTrees})
        result = super().avg_point_yield(**kwargs)

        scenario = Scenario.objects.get(id=kwargs.get('scenario_id'))
        feedstock = MaterialSettings.objects.get(id=kwargs.get('feedstock_id'))

        result['aggregated_distributions'] = []

        temporal_distribution = TemporalDistribution.objects.get(name='Summer/Winter')

        # Create the distribution for the stacked barchart seasonal production per component
        group = MaterialComponentGroup.objects.get(name='Macro Components')
        distribution = Distribution(
            TemporalDistribution.objects.get(name='Summer/Winter'),  # TODO: FIX me!!!!
            name='Seasonal production per component'
        )

        for agg_val in result['aggregated_values']:
            if agg_val['name'] == 'Total production':
                total_production = agg_val['value']
        inv_shares = feedstock.inventoryamountshare_set.filter(scenario=scenario)
        temp_dist = {timestep: inv_shares.get(timestep=timestep).average for timestep in temporal_distribution.timestep_set.all()}
        for share in feedstock.shares:
            if share.group_settings.group == group:
                if share.timestep.distribution == temporal_distribution:
                    value = share.average * temp_dist[share.timestep] * total_production
                    distribution.add_share(share.timestep, share.component, value)

        result['aggregated_distributions'].append(distribution.serialize())

        return result
