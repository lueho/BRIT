from django.db import connection

import gis_source_manager.models as gis_models
from scenario_builder.models import (InventoryAlgorithm,
                                     InventoryResultPointLayer,
                                     ScenarioInventoryConfiguration)


class BaseScenario:
    scenario = None
    region = None
    catchment = None

    def __init__(self, scenario=None):
        self.scenario = scenario
        self.region = scenario.region
        self.catchment = scenario.catchment


class GisInventory(BaseScenario):
    gis_source_model = None
    config = None
    results = None

    def __init__(self, *args, **kwargs):
        super(GisInventory, self).__init__(*args, **kwargs)
        self._load_inventory_config()

    @staticmethod
    def algorithm_does_not_exist():
        return 'The requested algorithm does not exist.'

    def _load_inventory_config(self):
        config_queryset = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario)

        inventory_config = {}
        for entry in config_queryset:
            function = entry.inventory_algorithm.function_name
            parameter = entry.inventory_parameter.short_name
            value = entry.inventory_value.value

            if function not in inventory_config.keys():
                inventory_config[function] = {}
            if parameter not in inventory_config[function]:
                inventory_config[function][parameter] = value

        self.config = inventory_config

    def _get_inventory_algorithm(self, name):
        return getattr(self, name)

    def run(self):
        self.results = {}
        if self.config:
            for alg, kwargs in self.config.items():
                inventory_algorithm = self._get_inventory_algorithm(alg)
                if alg not in self.results:
                    self.results[alg] = {}
                self.results[alg] = inventory_algorithm(**kwargs)

    def results_as_list(self):
        result_list = []
        for alg, res in self.results.items():
            result_list.append({'algorithm': alg, 'result': res})
        return result_list

    def create_result_model(self, algorithm_function_name):
        algorithm = InventoryAlgorithm.objects.get(function_name=algorithm_function_name)
        model_name = 'scenario_' + str(self.scenario.id) + '_algorithm_' + str(algorithm.id) + '_result'
        attrs = {'__module__': 'scenario_builder.models'}
        return type(model_name, (InventoryResultPointLayer,), attrs)

    # noinspection PyPep8Naming
    def save_result_table(self):
        for algorithm_function_name in self.config.keys():
            ResultModel = self.create_result_model(algorithm_function_name)
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(ResultModel)

            for record in self.results[algorithm_function_name]['queryset']:
                ResultModel.objects.create(
                    geom=record.geom,
                    average=10.1,
                    standard_deviation=0.2,
                )

    def set_gis_source_model(self, gis_source_model_name):
        self.gis_source_model = gis_models.CATALOGUE[gis_source_model_name]

    def avg_point_yield(self, avg=None):
        catchment = self.catchment
        trees_in_catchment = gis_models.HamburgRoadsideTrees.objects.filter(geom__intersects=catchment.geom)
        trees_count = trees_in_catchment.count()
        prunings_yield = avg * trees_count
        result = {
            'trees_count': trees_count,
            'total_yield': prunings_yield,
            'queryset': trees_in_catchment
        }
        return result

    @staticmethod
    def stupid_inventory(num1=None, num2=None):
        return num1 + num2
