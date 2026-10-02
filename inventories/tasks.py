from functools import partial

from celery import chord
from celery.result import AsyncResult
from celery.states import READY_STATES
from django.db import transaction

from brit.celery import app
from inventories.models import InventoryAlgorithm, RunningTask, Scenario, ScenarioStatus
from layer_manager.models import Layer
from materials.models import Material, SampleSeries


def _lock_scenario_status(scenario_id):
    return ScenarioStatus.objects.select_for_update().get(scenario_id=scenario_id)


def _has_active_running_tasks(running_tasks):
    return any(
        AsyncResult(str(task.uuid)).state not in READY_STATES for task in running_tasks
    )


def _set_running(scenario_status):
    scenario_status.status = ScenarioStatus.Status.RUNNING
    scenario_status.failed_algorithm = None
    scenario_status.failure_message = ""
    scenario_status.save(
        update_fields=["status", "failed_algorithm", "failure_message"]
    )


def start_inventory_run(scenario_id):
    """Claim the scenario for evaluation and enqueue run_inventory once.

    Returns False without enqueueing when a run is already pending or active.
    """
    with transaction.atomic():
        scenario_status = _lock_scenario_status(scenario_id)
        running_tasks = list(
            RunningTask.objects.select_for_update().filter(scenario_id=scenario_id)
        )
        if _has_active_running_tasks(running_tasks):
            return False
        if (
            scenario_status.status == ScenarioStatus.Status.RUNNING
            and not running_tasks
        ):
            return False
        _set_running(scenario_status)
        transaction.on_commit(partial(run_inventory.delay, scenario_id))
    return True


@app.task
def mark_inventory_failed(scenario_id, algorithm_id=None, failure_message=""):
    with transaction.atomic():
        scenario_status = (
            ScenarioStatus.objects.select_for_update()
            .filter(scenario_id=scenario_id)
            .first()
        )
        # RunningTask rows are kept: sibling algorithms of a failed chord may still
        # be executing and must keep blocking new runs until they are ready.
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
    try:
        with transaction.atomic():
            scenario_status = _lock_scenario_status(scenario_id)
            running_tasks = list(
                RunningTask.objects.select_for_update().filter(scenario_id=scenario_id)
            )
            if _has_active_running_tasks(running_tasks):
                return None
            RunningTask.objects.filter(
                id__in=[task.id for task in running_tasks]
            ).delete()
            # No task of an earlier run is active, so its staged results are orphaned.
            for layer in Layer.all_objects.filter(scenario_id=scenario_id, staged=True):
                layer.delete()
            _set_running(scenario_status)

            scenario = Scenario.objects.get(id=scenario_id)
            execution_plan = scenario.inventory_execution_plan()
            signatures = []
            for execution in execution_plan:
                signature = run_inventory_algorithm.s(
                    execution["algorithm"].id,
                    **execution["kwargs"],
                )
                signature.freeze()
                signatures.append(signature)
            layer_keys = [
                [execution["algorithm"].id, execution["kwargs"]["feedstock_id"]]
                for execution in execution_plan
            ]

            callback = finalize_inventory.s(scenario_id, layer_keys)
            callback.on_error(mark_inventory_failed.si(scenario_id))
            callback_id = callback.freeze().id
            task_chord = chord(signatures, callback)

            # Track task ids before dispatch so progress is visible from anywhere
            # and concurrent triggers see this run as active until the callback
            # has finalized it. The callback row has no algorithm.
            RunningTask.objects.bulk_create(
                [
                    *(
                        RunningTask(
                            scenario_id=scenario_id,
                            uuid=signature.id,
                            algorithm=execution["algorithm"],
                        )
                        for signature, execution in zip(
                            signatures, execution_plan, strict=True
                        )
                    ),
                    RunningTask(scenario_id=scenario_id, uuid=callback_id),
                ]
            )
            transaction.on_commit(partial(task_chord.apply_async, task_id=callback_id))
    except Exception as error:
        mark_inventory_failed.run(
            scenario_id,
            failure_message=str(error),
        )
        raise

    return [signature.id for signature in signatures]


@app.task(bind=True)
def run_inventory_algorithm(self, algorithm_id, **kwargs):
    algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
    scenario_id = kwargs["scenario_id"]
    try:
        results = algorithm.execute(**kwargs)
        layer_values = {
            "name": algorithm.function_name,
            "scenario": Scenario.objects.get(id=scenario_id),
            "feedstock": Material.objects.get(id=kwargs["feedstock_id"]),
            "sample_series": SampleSeries.objects.filter(
                id=kwargs.get("sample_series_id")
            ).first(),
            "algorithm": algorithm,
            "results": results,
        }
        Layer.objects.create_or_replace(staged=True, **layer_values)
    except Exception as error:
        mark_inventory_failed.run(
            scenario_id,
            algorithm.id,
            str(error),
        )
        raise
    return True


@app.task
def finalize_inventory(results, scenario_id, layer_keys=None):
    if not all(results):
        raise RuntimeError("Inventory algorithm did not complete.")

    with transaction.atomic():
        scenario_status = _lock_scenario_status(scenario_id)
        RunningTask.objects.filter(scenario_id=scenario_id).delete()
        current_layers = (
            None if layer_keys is None else {tuple(key) for key in layer_keys}
        )
        for layer in Layer.all_objects.filter(scenario_id=scenario_id, staged=True):
            if (
                current_layers is None
                or (layer.algorithm_id, layer.feedstock_id) in current_layers
            ):
                layer.publish()
            else:
                layer.delete()
        if current_layers is not None:
            for layer in Layer.objects.filter(scenario_id=scenario_id):
                if (layer.algorithm_id, layer.feedstock_id) not in current_layers:
                    layer.delete()
        scenario_status.status = ScenarioStatus.Status.FINISHED
        scenario_status.failed_algorithm = None
        scenario_status.failure_message = ""
        scenario_status.save(
            update_fields=["status", "failed_algorithm", "failure_message"]
        )
