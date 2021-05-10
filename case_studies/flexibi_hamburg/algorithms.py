from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
from flexibi_dst.models import TemporalDistribution
from material_manager.models import BaseObjects
from scenario_builder.algorithms import InventoryAlgorithmsBase


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
        distribution = TemporalDistribution.objects.get(name='Summer/Winter')  # TODO: FIX me!!!!
        components = [BaseObjects.objects.get.base_component]
        aggdist = {
            'name': 'Super name',
            'distribution': distribution.id,
            'sets': []
        }
        for timestep in distribution.timestep_set.all():
            distribution_set = {'timestep': timestep.id, 'shares': []}
            for component in components:
                distribution_set['shares'].append({'component': component.id, 'average': 2.5})
            aggdist['sets'].append(distribution_set)
        result['aggregated_distributions'].append(aggdist)

        return result
