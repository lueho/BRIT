from django.apps import apps

import gis_source_manager.models as gis_models
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
                fields = {}
                for key, value in self.results[algorithm_function_name]['features'][0].items():
                    fields[key] = type(value).__name__
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

    @staticmethod
    def stupid_inventory(num1=None, num2=None):
        return num1['value'] + num2['value']
