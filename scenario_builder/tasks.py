import importlib

from celery import chord

from flexibi_dst.celery import app
from layer_manager.models import Layer
from material_manager.models import MaterialSettings
from scenario_builder.models import InventoryAlgorithm, Scenario, ScenarioStatus
from scenario_evaluator.models import RunningTask


@app.task
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)

    scenario.set_status(ScenarioStatus.Status.RUNNING)

    scenario.delete_result_layers()

    signatures = []
    print(scenario.configuration_as_dict().items())
    for feedstock_id, config in scenario.configuration_as_dict().items():
        for function_name, kwargs in config.items():
            signatures.append(run_inventory_algorithm.s(function_name, **kwargs))

    callback = finalize_inventory.s(scenario.id)
    task_chord = chord(signatures, callback)
    result = task_chord.delay()

    # store uuids of running tasks in the database, so we can track the progress from anywhere
    for task in task_chord.tasks:
        source_module = task.args[0].split('.')[1]
        function_name = task.args[0].split(':')[1]
        algorithm = InventoryAlgorithm.objects.get(source_module=source_module, function_name=function_name)
        RunningTask.objects.create(scenario=scenario, uuid=task.id, algorithm=algorithm)

    return result


@app.task(bind=True)
def run_inventory_algorithm(self, module_function, **kwargs):
    source_module = module_function.split(':')[0]
    function_name = module_function.split(':')[1]
    module = importlib.import_module(source_module)
    results = getattr(module.InventoryAlgorithms, function_name)(**kwargs)
    algorithm = InventoryAlgorithm.objects.get(source_module=source_module.split('.')[1], function_name=function_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'feedstock': MaterialSettings.objects.get(id=kwargs.get('feedstock_id')),
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
    scenario.set_status(ScenarioStatus.Status.FINISHED)
