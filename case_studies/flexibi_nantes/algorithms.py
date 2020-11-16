from django.db.models import Sum

from scenario_builder.algorithms import InventoryAlgorithmsBase
from scenario_builder.models import Catchment, Scenario
from .models import NantesGreenhouses, Greenhouse


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def nantes_greenhouse_production(cls, **kwargs):

        catchment = Catchment.objects.get(id=kwargs.get('catchment_id'))
        clipped = NantesGreenhouses.objects.filter(geom__intersects=catchment.geom)
        scenario = Scenario.objects.get(id=kwargs.get('scenario_id'))

        component_list = []
        for feedstock in scenario.feedstocks():
            for component in feedstock.grouped_components()['Macro Components']:
                if component.name not in component_list:
                    component_list.append(component.name)

        result = {
            'aggregated_values': [],
            'aggregated_distributions': [],
            'features': []
        }

        total_production = 0

        for greenhouse_type in Greenhouse.objects.values('heated', 'lighted', 'high_wire', 'above_ground', 'nb_cycles',
                                                         'culture_1', 'culture_2', 'culture_3'):
            greenhouse_group = clipped.filter(**greenhouse_type)
            if greenhouse_group.exists():
                greenhouse = Greenhouse.objects.get(**greenhouse_type)
                total_group_surface = greenhouse_group.aggregate(Sum('surface_ha'))['surface_ha__sum']
                specific_annual_component_production = {}
                for component in component_list:
                    specific_distribution = greenhouse.seasonal_distributions.get(component__name=component).values
                    absolute_distribution = [value * total_group_surface for value in specific_distribution]
                    total_production += sum(absolute_distribution)
                    specific_annual_component_production[component] = sum(specific_distribution)
                    result['aggregated_distributions'].append({
                        'name': component,
                        'type': 'seasonal',
                        'distribution': absolute_distribution
                    })

                for feature in greenhouse_group:
                    fields = {f'total_{key}_production': feature.surface_ha * value for (key, value) in
                              specific_annual_component_production.items()}
                    fields['geom'] = feature.geom
                    result['features'].append(fields)

        result['aggregated_values'].append({
            'name': 'Total production',
            'value': total_production,
            'unit': 'Mg/a'
        })

        return result
