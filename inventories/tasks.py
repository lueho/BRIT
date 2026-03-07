from celery import chord

from brit.celery import app
from inventories.models import InventoryAlgorithm, RunningTask, Scenario, ScenarioStatus
from layer_manager.models import Layer
from materials.models import SampleSeries


@app.task
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)

    scenario.set_status(ScenarioStatus.Status.RUNNING)

    scenario.delete_result_layers()

    signatures = []
    for _feedstock_id, config in scenario.configuration_as_dict().items():
        for function_name, kwargs in config.items():
            signatures.append(run_inventory_algorithm.s(function_name, **kwargs))

    callback = finalize_inventory.s(scenario.id)
    task_chord = chord(signatures, callback)
    result = task_chord.delay()

    # store uuids of running tasks in the database, so we can track the progress from anywhere
    for task in task_chord.tasks:
        algorithm = InventoryAlgorithm.from_task_reference(task.args[0])
        RunningTask.objects.create(scenario=scenario, uuid=task.id, algorithm=algorithm)

    return result


@app.task(bind=True)
def run_inventory_algorithm(self, task_reference, **kwargs):
    algorithm = InventoryAlgorithm.from_task_reference(task_reference)
    module = algorithm.import_module()
    function_name = algorithm.function_name
    results = getattr(module.InventoryAlgorithms, function_name)(**kwargs)
    kwargs = {
        "name": algorithm.function_name,
        "scenario": Scenario.objects.get(id=kwargs.get("scenario_id")),
        "feedstock": SampleSeries.objects.get(id=kwargs.get("feedstock_id")),
        "algorithm": algorithm,
        "results": results,
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
    scenario.set_status(ScenarioStatus.Status.FINISHED)
