import importlib

from celery import group
from celery.result import AsyncResult
from django.conf import settings

from brit.celery import app
from inventories.models import Algorithm, Scenario, ScenarioStatus, RunningTask
from layer_manager.models import Layer
from materials.models import SampleSeries


@app.task
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)

    scenario.set_status(ScenarioStatus.Status.RUNNING)
    scenario.delete_result_layers()

    # Prepare task signatures and store information for tracking tasks
    signatures = []
    tasks_info = []
    for feedstock_id, config in scenario.configuration_as_dict().items():
        for function_name, kwargs in config.items():
            func_signature = run_inventory_algorithm.s(function_name, **kwargs)
            signatures.append(func_signature)
            tasks_info.append((function_name, kwargs))

    tasks_group = group(signatures).apply_async()
    monitor_tasks.delay(scenario_id)

    # Store uuids and related info of running tasks in the database
    for task_info, async_result in zip(tasks_info, tasks_group.children):
        function_name, kwargs = task_info
        source_module = function_name.split('.')[1]  # Assuming function_name includes module
        algorithm = Algorithm.objects.get(source_module=source_module, function_name=function_name.split(':')[1])
        RunningTask.objects.create(scenario=scenario, uuid=async_result.id, algorithm=algorithm)

    return tasks_group


@app.task(ignore_result=False)
def run_inventory_algorithm(module_function, **kwargs):
    source_module = module_function.split(':')[0]
    function_name = module_function.split(':')[1]
    module = importlib.import_module(source_module)
    results = getattr(module.InventoryAlgorithms, function_name)(**kwargs)
    algorithm = Algorithm.objects.get(source_module=source_module.split('.')[1], function_name=function_name)
    kwargs = {
        'name': algorithm.function_name,
        'scenario': Scenario.objects.get(id=kwargs.get('scenario_id')),
        'feedstock': SampleSeries.objects.get(id=kwargs.get('feedstock_id')),
        'algorithm': algorithm,
        'results': results
    }
    Layer.objects.create_or_replace(**kwargs)


@app.task
def finalize_inventory(scenario_id, final_status):
    RunningTask.objects.filter(scenario=scenario_id).delete()
    scenario = Scenario.objects.get(id=scenario_id)
    scenario.set_status(final_status)


@app.task
def handle_failed_inventory(task, scenario_id, **kwargs):
    """This task can be used to roll back changes from a failed inventory task and provide specific feedback."""
    pass


@app.task
def monitor_tasks(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)
    tasks = RunningTask.objects.filter(scenario=scenario)
    all_done = True
    all_successful = True

    for running_task in tasks:
        result = AsyncResult(str(running_task.uuid))
        if not result.ready():
            all_done = False
            break
        if not result.successful():
            all_successful = False

    if all_done:
        final_status = ScenarioStatus.Status.FINISHED if all_successful else ScenarioStatus.Status.FAILED
        finalize_inventory.delay(scenario_id, final_status)
    else:
        # Not all tasks are ready, reschedule the monitor_tasks to run after a short delay
        monitor_tasks.apply_async(args=[scenario_id], countdown=settings.MONITOR_TASKS_COUNTDOWN)
