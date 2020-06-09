from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.db.models import QuerySet

import gis_source_manager.models as gis_models
from gis_source_manager.models import HamburgGreenAreas
from layer_manager.models import Layer
from scenario_builder.models import InventoryAlgorithm
from .models import Catchment, Region, Scenario


class BaseScenario:
    scenario: Scenario = None
    region: Region = None
    catchment: Catchment = None

    def __init__(self, scenario=None):
        self.scenario = scenario
        self.region = scenario.region
        self.catchment = scenario.catchment


class EmptyQueryset(Exception):
    """The Queryset cannot be empty"""


class GisInventory(BaseScenario):
    config: dict = None
    results: dict = None

    def __init__(self, *args, **kwargs):
        super(GisInventory, self).__init__(*args, **kwargs)
        self.config = self.scenario.configuration_as_dict()

    def run(self):
        """
        Runs all algorithms that have been set up in self.config and creates layers in the database. Returns the
        instance of Layer and a feature_collection model that is dynamically generated in case the results contain
        geometric features. The feature_collection can be used to manage the features themselves, which are stored
        in an autimatically created separated table in the database.
        """

        # run the algorithms
        if self.config:
            self.results = {func_name: getattr(self, func_name)(**kwargs) for func_name, kwargs in self.config.items()}

        # create layers and store results in database
        created_layers = {}
        for function_name, results in self.results.items():
            algorithm = InventoryAlgorithm.objects.get(function_name=function_name)
            kwargs = {
                'name': algorithm.function_name,
                'scenario': self.scenario,
                'algorithm': algorithm,
                'results': results
            }
            layer, feature_collection = Layer.objects.create_or_replace(**kwargs)
            created_layers[layer] = feature_collection
        return created_layers

    def avg_point_yield(self, point_yield: dict = None):
        """
        Assignes a global average and standard deviation to all points that are found within the scenario catchment.
        :param point_yield: dict
        :return: result: dict
        """
        catchment = self.catchment
        trees_in_catchment = gis_models.HamburgRoadsideTrees.objects.filter(geom__intersects=catchment.geom)
        trees_count = trees_in_catchment.count()
        prunings_yield = point_yield['value'] * trees_count

        # If result is a gis layer, it must have a list of features under key ['features']. Each feature must have
        # an entry for the key 'geom'
        result = {
            'aggregated_values': {
                'trees_count': trees_count,
                'total_yield': prunings_yield,
            },
            'features': []
        }
        for tree in trees_in_catchment:
            result['features'].append({
                'geom': tree.geom,
                'point_yield_average': point_yield['value'],
                'point_yield_standard_deviation': point_yield['standard_deviation']
            })
        return result

    def avg_area_yield(self, area_yield: dict = None):
        """
        Assignes a global average and standard deviation to park areas that where found in the scenario catchment.
        :param area_yield:
        :return:
        """
        input_qs = HamburgGreenAreas.objects.all()
        mask_qs = Catchment.objects.filter(id=self.catchment.id)
        keep_columns = ['anlagenname', 'belegenheit', 'gruenart', 'nutzcode']
        clipped_polygons = self.clip_polygons(input_qs, mask_qs, keep_columns=keep_columns)
        result = {
            'aggregated_values': {
                'total_area': 0,
                'total_yield_average': 0
            },
            'features': []
        }
        for polygon in clipped_polygons:
            result['aggregated_values']['total_area'] += polygon['area']
            result['aggregated_values']['total_yield_average'] += polygon['area'] * area_yield['value']
            result['features'].append({
                'geom': polygon['geom'],
                'area': polygon['area'],
                'yield_average': polygon['area'] * area_yield['value'],
                'name': polygon['anlagenname'],
                'usage': polygon['gruenart']})

        return result

    @staticmethod
    def clip_polygons(input_qs: QuerySet, mask_qs: QuerySet, keep_columns: [str] = None):

        if not input_qs:
            raise EmptyQueryset

        if not mask_qs:
            raise EmptyQueryset

        # Clean up column names and remove any non existing column names
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

        input_table_name = input_qs.model._meta.db_table
        input_ids = '(' + ', '.join(str(id_) for id_ in input_qs.values_list('id', flat=True)) + ')'
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
