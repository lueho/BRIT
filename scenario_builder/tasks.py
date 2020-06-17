from celery import shared_task, current_task

from layer_manager.models import Layer
from scenario_builder.inventory_algorithms import InventoryAlgorithms
from scenario_builder.models import Scenario, InventoryAlgorithm


@shared_task
def run_inventory_algorithm(function_name, **kwargs):
    results = getattr(InventoryAlgorithms, function_name)(**kwargs)
    algorithm = InventoryAlgorithm.objects.get(function_name=function_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'algorithm': algorithm,
        'results': results
    }
    Layer.objects.create_or_replace(**kwargs)

    current_task.update_status(status='PENDING')

    return True
