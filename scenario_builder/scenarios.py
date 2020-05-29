from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.db.models import QuerySet

import gis_source_manager.models as gis_models
from gis_source_manager.models import HamburgGreenAreas
from layer_manager.models import Layer
from scenario_builder.models import (InventoryAlgorithm,
                                     ScenarioInventoryConfiguration)
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
    gis_source_model = None
    config: dict = None
    results: dict = None

    def __init__(self, *args, **kwargs):
        super(GisInventory, self).__init__(*args, **kwargs)
        self._load_inventory_config()

    def _load_inventory_config(self):
        """
        Fetches all configuration entries that are associated with this scenario and assembles a dictionary holding
        all configuration information for the inventory.
        :return: None
        """
        config_queryset = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario)

        inventory_config = {}
        for entry in config_queryset:
            function = entry.inventory_algorithm.function_name
            parameter = entry.inventory_parameter.short_name
            value = entry.inventory_value.value
            standard_deviation = entry.inventory_value.standard_deviation

            if function not in inventory_config.keys():
                inventory_config[function] = {}
            if parameter not in inventory_config[function]:
                inventory_config[function][parameter] = {'value': value, 'standard_deviation': standard_deviation}

        self.config = inventory_config

    def _get_inventory_algorithm(self, function_name: str):
        return getattr(self, function_name)

    def run(self):
        self.results = {}
        if self.config:
            for func, kwargs in self.config.items():
                inventory_algorithm = self._get_inventory_algorithm(func)
                if func not in self.results:
                    self.results[func] = {}
                self.results[func] = inventory_algorithm(**kwargs)
        self._save_results_in_database()

    def results_as_list(self):
        result_list = []
        for alg, res in self.results.items():
            result_list.append({'algorithm': alg, 'result': res})
        return result_list

    def _save_results_in_database(self):
        """
        Goes through the inventory results to create a layer for each result and store them in the database.
        :return: None
        """
        result_layers = []
        for algorithm_function_name in self.config.keys():
            if self.results[algorithm_function_name]['features']:
                geom_type = type(self.results[algorithm_function_name]['features'][0]['geom'])
                algorithm = InventoryAlgorithm.objects.get(function_name=algorithm_function_name)

                features = self.results[algorithm_function_name]['features']
                fields = {}
                # The data types of the fields are detected from their content. Any column that has only null values
                # will be omitted completely
                fields_with_unknown_datatype = list(features[0].keys())
                for feature in features:
                    if not fields_with_unknown_datatype:
                        break
                    for key, value in feature.items():
                        if feature[key] and key in fields_with_unknown_datatype:
                            fields[key] = type(value).__name__
                            fields_with_unknown_datatype.remove(key)

                # At this point there might be fields left out because there were only null values from which the
                # data type could be detected. They should be omitted but this information should be logged
                # TODO: add omitted columns info to log

                fields.pop('geom')

                result_layer = Layer.objects.create_or_replace_layer(name=algorithm_function_name,
                                                                     geom_type=geom_type,
                                                                     scenario=self.scenario,
                                                                     algorithm=algorithm,
                                                                     fields=fields)

                result_model = result_layer.get_layer_model()
                for feature in self.results[algorithm_function_name]['features']:
                    result_model.objects.create(**feature)

        return result_layers

    def set_gis_source_model(self, gis_source_model_name: str):
        """
        Fetches the model class for a given model class function_name. The model must be registered in
        gis_source_manager.models.CATALOGUE.
        :param gis_source_model_name: str
        :return: class
        """
        self.gis_source_model = apps.all_models['gis_source_manager'][gis_source_model_name.lower()]

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
            'trees_count': trees_count,
            'total_yield': prunings_yield,
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
            'total_area': 0,
            'total_yield_average': 0,
            'features': []
        }
        for polygon in clipped_polygons:
            result['total_area'] += polygon['area']
            result['total_yield_average'] += polygon['area'] * area_yield['value']
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
        input_ids = '(' + ', '.join(str(id) for id in input_qs.values_list('id', flat=True)) + ')'
        mask_table_name = mask_qs.model._meta.db_table
        mask_ids = '(' + ', '.join(str(id) for id in mask_qs.values_list('id', flat=True)) + ')'

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
