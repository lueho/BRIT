from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
from distributions.plots import Distribution
from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import Scenario
from materials.models import SampleSeries


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
        feedstock = SampleSeries.objects.get(id=kwargs.get('feedstock_id'))

        result['aggregated_distributions'] = []

        inv_shares = feedstock.inventoryamountshare_set.filter(
            scenario=scenario
        ).select_related('timestep__distribution')
        if not inv_shares.exists():
            return result

        temporal_distribution = inv_shares.first().timestep.distribution

        # Create the distribution for the stacked barchart seasonal production per component
        distribution = Distribution(
            temporal_distribution,
            name='Seasonal production per component'
        )

        total_production = 0
        for agg_val in result['aggregated_values']:
            if agg_val['name'] == 'Total production':
                total_production = agg_val['value']
        temp_dist = {share.timestep_id: share.average for share in inv_shares}
        macro_component_shares = [
            share
            for share in feedstock.shares
            if share.group_settings.group.name == 'Macro Components'
        ]
        seasonal_component_shares = [
            share
            for share in macro_component_shares
            if share.timestep.distribution_id == temporal_distribution.id
        ]

        if seasonal_component_shares:
            for share in seasonal_component_shares:
                amount_share = temp_dist.get(share.timestep.id)
                if amount_share is None:
                    continue
                value = (
                    float(share.average)
                    * float(amount_share)
                    * float(total_production)
                )
                distribution.add_share(share.timestep, share.component, value)
        else:
            average_component_shares = [
                share
                for share in macro_component_shares
                if share.timestep.distribution.name == 'Average'
            ]
            for inv_share in inv_shares:
                for share in average_component_shares:
                    value = (
                        float(share.average)
                        * float(inv_share.average)
                        * float(total_production)
                    )
                    distribution.add_share(inv_share.timestep, share.component, value)

        result['aggregated_distributions'].append(distribution.serialize())

        return result
