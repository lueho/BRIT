from typing import List

from scenario_builder.models import InventoryAlgorithm
from scenario_builder.tasks import run_inventory_algorithm
from .models import Catchment, Region, Scenario


class BaseScenario:
    scenario: Scenario = None
    region: Region = None
    catchment: Catchment = None
    running_tasks: List[object] = None

    def __init__(self, scenario=None):
        self.scenario = scenario
        self.region = scenario.region
        self.catchment = scenario.catchment
        self.running_tasks = []


class GisInventory(BaseScenario):
    config: dict = None
    results: dict = None

    def __init__(self, *args, **kwargs):
        super(GisInventory, self).__init__(*args, **kwargs)
        self.config = self.scenario.configuration_as_dict()

    def start_evaluation(self):
        """
        Runs all algorithms that have been set up in self.config and creates layers in the database. Returns the
        instance of Layer and a feature_collection model that is dynamically generated in case the results contain
        geometric features. The feature_collection can be used to manage the features themselves, which are stored
        in an autimatically created separated table in the database.
        """

        for function_name, kwargs in self.config.items():
            task = run_inventory_algorithm.delay(function_name, **kwargs)
            algorithm = InventoryAlgorithm.objects.get(function_name=function_name)
            self.running_tasks.append({
                'task_id': task.id,
                'algorithm_name': algorithm.name,
            })
