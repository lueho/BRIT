from flexibi_dst.celery import app

from layer_manager.models import Layer
from scenario_builder.inventory_algorithms import InventoryAlgorithms
from scenario_builder.models import Scenario, InventoryAlgorithm


@app.task(bind=True)
def run_inventory_algorithm(self, function_name, **kwargs):
    results = getattr(InventoryAlgorithms, function_name)(**kwargs)
    algorithm = InventoryAlgorithm.objects.get(function_name=function_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'algorithm': algorithm,
        'results': results
    }
    Layer.objects.create_or_replace(**kwargs)

    return True


@app.task
def unblock_scenario(results, scenario_id):
    if not all(results):
        raise Exception
    scenario = Scenario.objects.get(id=scenario_id)
    scenario.evaluation_running = False
    scenario.save()
