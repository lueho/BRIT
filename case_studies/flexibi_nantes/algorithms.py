from django.db.models import Sum

from scenario_builder.algorithms import InventoryAlgorithmsBase
from scenario_builder.models import Catchment, Material
from .models import NantesGreenhouses, Greenhouse


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def nantes_greenhouse_production(cls, **kwargs):
        """

        :param kwargs: catchment_id, scenario_id
        :return:
        """

        catchment = Catchment.objects.get(id=kwargs.get('catchment_id'))
        clipped = NantesGreenhouses.objects.filter(geom__intersects=catchment.geom)
        feedstock = Material.objects.get(id=kwargs.get('feedstock_id'))

        component_list = []
        for component in feedstock.grouped_components()['Macro Components']['components']:
            if component not in component_list:
                component_list.append(component)

        print(component_list)

        result = {
            'aggregated_values': [],
            'aggregated_distributions': [],
            'features': []
        }

        total_production = 0

        for greenhouse_type in Greenhouse.objects.types():
            if 'culture_2' not in greenhouse_type:
                greenhouse_type.update({'culture_2': None})
            if 'culture_3' not in greenhouse_type:
                greenhouse_type.update({'culture_3': None})
            print('greenhouse type: ', greenhouse_type)
            greenhouse_group = clipped.filter(**greenhouse_type)
            if greenhouse_group.exists():
                total_group_surface = greenhouse_group.aggregate(Sum('surface_ha'))['surface_ha__sum']
                print('group surface: ', total_group_surface)
                greenhouse = Greenhouse.objects.get(**greenhouse_type)
                specific_annual_component_production = {}
                for component in component_list:
                    if component in greenhouse.components():
                        specific_distributions = [cycle.values for cycle in greenhouse.growth_cycles.filter(component=component)]
                        specific_distribution = [sum(values) for values in zip(*specific_distributions)]
                        print(specific_distributions)
                        absolute_distribution = [value * total_group_surface for value in specific_distribution]
                        print(absolute_distribution)
                        total_production += sum(absolute_distribution)
                        specific_annual_component_production[component] = sum(specific_distribution)
                        current_distribution = None
                        for dist in result['aggregated_distributions']:
                            dist_name = f'{component.material.name}: {component.name}'
                            if dist['name'] == dist_name:
                                current_distribution = dist
                                break
                        if not current_distribution:
                            current_distribution = {
                                'name': f'{component.material.name}: {component.name}',
                                'type': 'seasonal',
                                'distribution': [0] * 12
                            }
                            result['aggregated_distributions'].append(current_distribution)

                        current_distribution['distribution'] = [sum(x) for x in
                                                zip(current_distribution['distribution'], absolute_distribution)]
                        print(current_distribution)
                    else:
                        print('component not found')

                for feature in greenhouse_group:
                    fields = {'geom': feature.geom}
                    # fields = {f'total_{key}_production': feature.surface_ha * value for (key, value) in
                    #           specific_annual_component_production.items()}
                    result['features'].append(fields)

        result['aggregated_values'].append({
            'name': 'Total production',
            'value': total_production * 1000,
            'unit': 'Mg/a'
        })

        return result
