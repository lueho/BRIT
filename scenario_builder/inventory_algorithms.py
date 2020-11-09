from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.db.models import QuerySet

import gis_source_manager.models as gis_models
from case_study_nantes.models import NantesGreenhouses
from gis_source_manager.models import HamburgGreenAreas
from scenario_builder.models import Catchment
from .exceptions import EmptyQueryset


class InventoryAlgorithms(object):

    @staticmethod
    def avg_point_yield(**kwargs):
        """
        Assignes a global average and standard deviation to all points that are found within the scenario catchment.
        Required keyword arguments:
        catchment_id
        point_yield = {'value': <value>, 'standard_deviation': <std>}
        """
        catchment = Catchment.objects.get(id=kwargs.get('catchment_id'))
        trees_in_catchment = gis_models.HamburgRoadsideTrees.objects.filter(geom__intersects=catchment.geom)
        trees_count = trees_in_catchment.count()
        point_yield = kwargs.get('point_yield')
        prunings_yield = point_yield['value'] * trees_count

        # If result is a gis layer, it must have a list of features under key ['features']. Each feature must have
        # an entry for the key 'geom'
        result = {
            'aggregated_values': [
                {
                    'name': 'Number of trees',
                    'value': trees_count,
                    'unit': ''
                },
                {
                    'name': 'Total production',
                    'value': prunings_yield,
                    'unit': 'kg'
                }
            ],
            'features': []
        }
        for tree in trees_in_catchment:
            result['features'].append({
                'geom': tree.geom,
                'point_yield_average': point_yield['value'],
                'point_yield_standard_deviation': point_yield['standard_deviation']
            })
        return result

    @staticmethod
    def avg_area_yield(**kwargs):
        """
        Assignes a global average and standard deviation to park areas that where found in the scenario catchment.
        Required keyword arguments:
        - catchment_id
        - area_yield: {'value': <value>}
        """
        input_qs = HamburgGreenAreas.objects.all()
        mask_qs = Catchment.objects.filter(id=kwargs.get('catchment_id'))
        keep_columns = ['anlagenname', 'belegenheit', 'gruenart', 'nutzcode']
        clipped_polygons = InventoryAlgorithms.clip_polygons(input_qs, mask_qs, keep_columns=keep_columns)
        result = {
            'aggregated_values': [
                {
                    'name': 'Total area',
                    'value': 0,
                    'unit': 'm²'
                },
                {
                    'name': 'Total production',
                    'value': 0,
                    'unit': 'kg'
                }
            ],
            'features': []
        }

        area_yield = kwargs.get('area_yield')
        for polygon in clipped_polygons:
            result['aggregated_values'][0]['value'] += polygon['area']
            result['aggregated_values'][1]['value'] += polygon['area'] * area_yield['value']
            result['features'].append({
                'geom': polygon['geom'],
                'area': polygon['area'],
                'yield_average': polygon['area'] * area_yield['value'],
                'name': polygon['anlagenname'],
                'usage': polygon['gruenart']})

        return result

    @staticmethod
    def nantes_greenhouse_yield(**kwargs):
        catchment = Catchment.objects.get(id=kwargs.get('catchment_id'))
        greenhouses_in_catchment = NantesGreenhouses.objects.filter(geom__intersects=catchment.geom)
        greenhouses_count = greenhouses_in_catchment.count()

        point_yield = kwargs.get('point_yield')
        total_production = point_yield['value'] * greenhouses_count

        component_list = ['Cucumber leaves', 'Cucumber stems', 'Cucumber fruit']
        distribution = [1.2, 1.3, 1.2, 1.3, 1.2, 1.3, 1.2, 1.3, 1.2, 1.3, 1.2, 1.3]

        result = {
            'aggregated_values': [
                {
                    'name': 'Number of greenhouses',
                    'value': greenhouses_count,
                    'unit': ''
                },
                {
                    'name': 'Total production',
                    'value': total_production,
                    'unit': 'kg'
                }
            ],
            'aggregated_distributions': [],
            'features': []
        }
        for greenhouse in greenhouses_in_catchment:
            result['features'].append({
                'geom': greenhouse.geom,
                'point_yield_average': point_yield['value'],
                'point_yield_standard_deviation': point_yield['standard_deviation']
            })
        for component in component_list:
            result['aggregated_distributions'].append({
                'name': component,
                'type': 'seasonal',
                'distribution': distribution
            })

        return result

    @staticmethod
    def clip_polygons(input_qs: QuerySet, mask_qs: QuerySet, keep_columns: [str] = None):

        if not input_qs:
            raise EmptyQueryset

        if not mask_qs:
            raise EmptyQueryset

        # Clean up column names and remove any non existing column names
        # noinspection PyProtectedMember
        input_fields_names = [field.name for field in input_qs.model._meta.get_fields()]
        columns = []
        if keep_columns is not None:
            for column_name in keep_columns:
                if column_name in input_fields_names:
                    columns.append(column_name)

        if columns:
            columns_str = ', '.join(['input.' + name for name in columns]) + ','
        else:
            columns_str = ''

        # noinspection PyProtectedMember
        input_table_name = input_qs.model._meta.db_table
        input_ids = '(' + ', '.join(str(id_) for id_ in input_qs.values_list('id', flat=True)) + ')'
        # noinspection PyProtectedMember
        mask_table_name = mask_qs.model._meta.db_table
        mask_ids = '(' + ', '.join(str(id_) for id_ in mask_qs.values_list('id', flat=True)) + ')'

        # Query based on: https://postgis.net/docs/ST_Intersection.html
        query = f"""-- noinspection SqlResolve
                        SELECT clipped.*, ST_Area(clipped.geom::geography) AS area
                        FROM (
                            SELECT
                                {columns_str}
                                ST_Multi(
                                    ST_Buffer(ST_Intersection(mask.geom, input.geom), 0.0)
                                ) AS geom
                            FROM (SELECT * FROM {input_table_name} WHERE id IN {input_ids}) AS input
                            INNER JOIN (SELECT geom FROM {mask_table_name} WHERE id IN {mask_ids}) mask
                            ON ST_Intersects(mask.geom, input.geom)
                            WHERE NOT ST_IsEmpty(ST_Buffer(ST_Intersection(mask.geom, input.geom), 0.0))) clipped;
                    """

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            features = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        # The cursor gets the geometry only as string representation. Create a geometry objects from it with GEOS API
        for feature in features:
            feature['geom'] = GEOSGeometry(feature['geom'])

        return features
