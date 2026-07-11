from celery import chord
from django.db import transaction

from brit.celery import app
from inventories.models import InventoryAlgorithm, RunningTask, Scenario, ScenarioStatus
from layer_manager.models import Layer
from materials.models import SampleSeries


@app.task
def mark_inventory_failed(scenario_id, algorithm_id=None, failure_message=""):
    with transaction.atomic():
        scenario_status = (
            ScenarioStatus.objects.select_for_update()
            .filter(scenario_id=scenario_id)
            .first()
        )
        RunningTask.objects.filter(scenario_id=scenario_id).delete()
        if scenario_status is None or scenario_status.status not in {
            ScenarioStatus.Status.RUNNING,
            ScenarioStatus.Status.FAILED,
        }:
            return

        scenario_status.status = ScenarioStatus.Status.FAILED
        update_fields = ["status"]
        if algorithm_id is not None:
            scenario_status.failed_algorithm_id = algorithm_id
            update_fields.append("failed_algorithm")
        if failure_message:
            scenario_status.failure_message = failure_message
            update_fields.append("failure_message")
        scenario_status.save(update_fields=update_fields)


@app.task
def run_inventory(scenario_id):
    scenario = Scenario.objects.get(id=scenario_id)

    scenario.set_status(ScenarioStatus.Status.RUNNING)

    try:
        scenario.delete_result_layers()

        execution_plan = scenario.inventory_execution_plan()
        signatures = []
        for execution in execution_plan:
            signatures.append(
                run_inventory_algorithm.s(
                    execution["algorithm"].id,
                    **execution["kwargs"],
                )
            )

        callback = finalize_inventory.s(scenario.id)
        callback.on_error(mark_inventory_failed.si(scenario.id))
        task_chord = chord(signatures, callback)
        result = task_chord.delay()

        # store uuids of running tasks in the database, so we can track the progress from anywhere
        for task, execution in zip(task_chord.tasks, execution_plan, strict=False):
            RunningTask.objects.create(
                scenario=scenario,
                uuid=task.id,
                algorithm=execution["algorithm"],
            )
    except Exception as error:
        mark_inventory_failed.run(
            scenario.id,
            failure_message=str(error),
        )
        raise

    return result


@app.task(bind=True)
def run_inventory_algorithm(self, algorithm_id, **kwargs):
    algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
    scenario_id = kwargs["scenario_id"]
    try:
        results = algorithm.execute(**kwargs)
        layer_values = {
            "name": algorithm.function_name,
            "scenario": Scenario.objects.get(id=scenario_id),
            "feedstock": SampleSeries.objects.get(id=kwargs["feedstock_id"]),
            "algorithm": algorithm,
            "results": results,
        }
        Layer.objects.create_or_replace(**layer_values)
    except Exception as error:
        mark_inventory_failed.run(
            scenario_id,
            algorithm.id,
            str(error),
        )
        raise
    return True


@app.task
def finalize_inventory(results, scenario_id):
    if not all(results):
        raise Exception

    # remove finished tasks from db
    RunningTask.objects.filter(scenario=scenario_id).delete()
    scenario = Scenario.objects.get(id=scenario_id)
    scenario.set_status(ScenarioStatus.Status.FINISHED)
