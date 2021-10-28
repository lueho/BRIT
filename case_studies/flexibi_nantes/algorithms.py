from django.db.models import Sum

from distributions.plots import Distribution
from flexibi_dst.models import TemporalDistribution
from scenario_builder.algorithms import InventoryAlgorithmsBase
from scenario_builder.models import Scenario
from materials.models import MaterialSettings
from .models import NantesGreenhouses, Greenhouse


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def nantes_greenhouse_production(cls, **kwargs):
        """
        Here all the algorithms that are specific to the case study of the greenhouses in Nantes region are implemented.
        """
        scenario = Scenario.objects.get(id=kwargs.get('scenario_id'))
        feedstock = MaterialSettings.objects.get(id=kwargs.get('feedstock_id'))
        catchment = scenario.catchment

        result = {
            'aggregated_values': [],
            'aggregated_distributions': [],
            'features': []
        }

        # Get all greenhouse data within the scenario catchment
        clipped = NantesGreenhouses.objects.filter(geom__intersects=catchment.geom)

        # Filter the greenhouse types
        filter_kwargs = {}
        heated = kwargs.get('heated')['value']
        if heated < 2:
            filter_kwargs['heated'] = bool(heated)
        lit = kwargs.get('lit')['value']
        if lit < 2:
            filter_kwargs['lighted'] = bool(lit)
        high_wire = kwargs.get('high_wire')['value']
        if high_wire < 2:
            filter_kwargs['high_wire'] = bool(high_wire)
        above_ground = kwargs.get('above_ground')['value']
        if above_ground < 2:
            filter_kwargs['above_ground'] = bool(above_ground)

        greenhouse_types = Greenhouse.objects.filter(**filter_kwargs)

        # filter the clipped layer
        clipped_filtered = NantesGreenhouses.objects.none()
        for greenhouse_type in greenhouse_types:
            clipped_filtered = clipped_filtered.union(NantesGreenhouses.objects.filter(**greenhouse_type.filter_kwargs))

        # Create the distribution for the stacked barchart seasonal production per component
        distribution = Distribution(
            TemporalDistribution.objects.get(name='Months of the year'),
            name='Seasonal production per component'
        )

        # Initialize aggregated values
        total_surface = 0
        total_production = 0
        greenhouse_count = 0

        # Filter the greenhouse dataset by type of greenhouse and apply specific values
        for greenhouse_type in greenhouse_types:
            if feedstock.culture_set.first().name in list(greenhouse_type.cultures().values()):
                greenhouse_group = clipped.filter(**greenhouse_type.filter_kwargs)
                if greenhouse_group.exists():
                    greenhouse_group.filter(culture_1=greenhouse_type.filter_kwargs['culture_1'])
                    total_group_surface = greenhouse_group.aggregate(Sum('surface_ha'))['surface_ha__sum']
                    total_surface += total_group_surface
                    greenhouse_count += greenhouse_group.count()
                    for share in greenhouse_type.shares:
                        if share.timestepset.growth_cycle.culture.residue == feedstock:
                            distribution.add_share(share.timestepset.timestep, share.component,
                                                   total_group_surface * share.average)
                            total_production += total_group_surface * share.average

        result['aggregated_distributions'].append(distribution.serialize())

        result['aggregated_values'].append({
            'name': 'Number of considered greenhouses',
            'value': greenhouse_count,
            'unit': ''})

        result['aggregated_values'].append({
            'name': 'Total growth area',
            'value': total_surface,
            'unit': 'ha'})

        result['aggregated_values'].append({
            'name': 'Total production',
            'value': total_production,
            'unit': 'Mg/a'
        })

        for feature in clipped_filtered:
            fields = {'geom': feature.geom}
            result['features'].append(fields)

        return result
