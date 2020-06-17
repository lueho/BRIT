from celery import shared_task, current_task

from layer_manager.models import Layer
from scenario_builder.models import Scenario, InventoryAlgorithm
from scenario_builder.scenarios import GisInventory


@shared_task()
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)
    inventory = GisInventory(scenario)
    inventory.run()
    return True


@shared_task
def run_inventory_algorithm(algorithm_name, **kwargs):
    results = getattr(GisInventory, algorithm_name)(**kwargs)
    algorithm = InventoryAlgorithm.objects.get(function_name=algorithm_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'algorithm': algorithm,
        'results': results
    }
    Layer.objects.create_or_replace(**kwargs)

    current_task.update_status(status='PENDING', meta={'algorithm_name': algorithm_name})

    return True
