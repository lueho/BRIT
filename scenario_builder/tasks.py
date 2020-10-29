from celery import chord

from flexibi_dst.celery import app
from layer_manager.models import Layer
from scenario_builder.inventory_algorithms import InventoryAlgorithms
from scenario_builder.models import InventoryAlgorithm, Material, Scenario, ScenarioStatus
from scenario_evaluator.models import RunningTask


@app.task
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)

    scenario.set_status(ScenarioStatus.Status.RUNNING)

    scenario.delete_result_layers()

    signatures = []
    for feedstock_id, config in scenario.configuration_as_dict().items():
        for function_name, kwargs in config.items():
            signatures.append(run_inventory_algorithm.s(function_name, **kwargs))

    callback = finalize_inventory.s(scenario.id)
    task_chord = chord(signatures, callback)
    result = task_chord.delay()

    # store uuids of running tasks in the database, so we can track the progress from anywhere
    for task in task_chord.tasks:
        algorithm = InventoryAlgorithm.objects.get(function_name=task.args[0])
        RunningTask.objects.create(scenario=scenario, uuid=task.id, algorithm=algorithm)

    return result


@app.task(bind=True)
def run_inventory_algorithm(self, function_name, **kwargs):
    results = getattr(InventoryAlgorithms, function_name)(**kwargs)
    algorithm = InventoryAlgorithm.objects.get(function_name=function_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'feedstock': Material.objects.get(id=kwargs.get('feedstock_id')),
        'algorithm': algorithm,
        'results': results
    }
    Layer.objects.create_or_replace(**kwargs)

    return True


@app.task
def finalize_inventory(results, scenario_id):
    if not all(results):
        raise Exception

    # remove finished tasks from db
    RunningTask.objects.filter(scenario=scenario_id).delete()
    scenario = Scenario.objects.get(id=scenario_id)
    scenario.set_status(ScenarioStatus.Status.CHANGED)
