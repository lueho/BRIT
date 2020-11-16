from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
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
        return super().avg_point_yield(**kwargs)
