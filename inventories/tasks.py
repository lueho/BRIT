"""Run-fenced inventory evaluation.

Drain old workers and queued tasks before activating this task protocol.
Legacy NULL attempt identities are neither guessed nor accepted.
"""

import logging
import uuid
from functools import partial

from celery import chord
from celery.states import READY_STATES
from django.db import transaction
from django.db.utils import OperationalError

from brit.celery import app
from inventories.models import (
    InventoryAlgorithm,
    RunningTask,
    ScenarioStatus,
    is_backend_task_active,
    is_current_inventory_run,
    locked_scenario_evaluation,
)
from layer_manager.models import Layer
from materials.models import Material, SampleSeries

logger = logging.getLogger(__name__)


def _set_running(scenario_status, run_id):
    scenario_status.status = ScenarioStatus.Status.RUNNING
    scenario_status.failed_algorithm = None
    scenario_status.failure_message = ""
    scenario_status.run_id = run_id
    scenario_status.save(
        update_fields=["status", "failed_algorithm", "failure_message", "run_id"]
    )


def _safe_enqueue_settlement(scenario_id, run_id):
    """Best-effort settlement enqueue; must never mask the primary error."""
    try:
        settle_failed_inventory_run.delay(scenario_id, str(run_id))
    except Exception:
        logger.warning(
            "Failed to enqueue settlement for scenario %s run %s",
            scenario_id,
            run_id,
        )


def _header_tasks_ready(running_tasks, run_id):
    """True when every algorithm-bearing row of `run_id` is backend-terminal."""
    run_id = uuid.UUID(str(run_id))
    headers = [
        task
        for task in running_tasks
        if task.algorithm_id is not None and task.run_id == run_id
    ]
    return all(not is_backend_task_active(task.uuid) for task in headers)


def start_inventory_run(scenario_id):
    """Claim the scenario for evaluation and enqueue run_inventory once.

    Returns False without enqueueing when a run is already pending or active.
    """
    with locked_scenario_evaluation(scenario_id) as locked:
        if locked is None:
            return False
        _, scenario_status, running_tasks = locked
        settled_failure = (
            scenario_status.status == ScenarioStatus.Status.FAILED
            and scenario_status.run_id is not None
            and _header_tasks_ready(running_tasks, scenario_status.run_id)
        )
        # A failed chord's callback need not execute once all its headers are
        # terminal. Other generations and legacy unknown rows still block.
        blocking_tasks = (
            task
            for task in running_tasks
            if not (settled_failure and task.run_id == scenario_status.run_id)
        )
        if any(is_backend_task_active(task.uuid) for task in blocking_tasks):
            return False
        if (
            scenario_status.status == ScenarioStatus.Status.RUNNING
            and not running_tasks
        ):
            return False
        # Do not remove any markers until every claim guard has passed.
        RunningTask.objects.filter(id__in=[task.id for task in running_tasks]).delete()
        for layer in Layer.all_objects.filter(scenario_id=scenario_id, staged=True):
            layer.delete()
        new_run_id = uuid.uuid4()
        _set_running(scenario_status, new_run_id)
        transaction.on_commit(
            partial(run_inventory.delay, scenario_id, str(new_run_id))
        )
    return True


@app.task
def mark_inventory_failed(scenario_id, run_id, algorithm_id=None, failure_message=""):
    """Fenced failure write: only mutates while run_id is the current attempt."""
    with locked_scenario_evaluation(scenario_id) as locked:
        if locked is None:
            return
        _, scenario_status, _ = locked
        if not is_current_inventory_run(scenario_status, run_id):
            return
        if scenario_status.status not in {
            ScenarioStatus.Status.RUNNING,
            ScenarioStatus.Status.FAILED,
        }:
            return
        scenario_status.status = ScenarioStatus.Status.FAILED
        update_fields = ["status"]
        if scenario_status.failed_algorithm_id is None:
            if algorithm_id is not None:
                # First specific failure writes the algorithm+message pair.
                scenario_status.failed_algorithm_id = algorithm_id
                update_fields.append("failed_algorithm")
                scenario_status.failure_message = failure_message
                update_fields.append("failure_message")
            elif failure_message and not scenario_status.failure_message:
                scenario_status.failure_message = failure_message
                update_fields.append("failure_message")
        elif (
            algorithm_id == scenario_status.failed_algorithm_id
            and failure_message
            and not scenario_status.failure_message
        ):
            scenario_status.failure_message = failure_message
            update_fields.append("failure_message")
        scenario_status.save(update_fields=update_fields)
        transaction.on_commit(partial(_safe_enqueue_settlement, scenario_id, run_id))


@app.task
def run_inventory(scenario_id, run_id):
    try:
        with locked_scenario_evaluation(scenario_id) as locked:
            if locked is None:
                return None
            scenario, scenario_status, running_tasks = locked
            if not is_current_inventory_run(scenario_status, run_id) or (
                scenario_status.status != ScenarioStatus.Status.RUNNING
            ):
                return None
            if running_tasks:
                # A duplicate launch of this generation never relaunches the chord.
                return None
            for layer in Layer.all_objects.filter(scenario_id=scenario_id, staged=True):
                layer.delete()
            execution_plan = scenario.inventory_execution_plan()
            signatures = []
            for execution in execution_plan:
                signature = run_inventory_algorithm.s(
                    execution["algorithm"].id,
                    run_id=str(run_id),
                    **execution["kwargs"],
                )
                signature.freeze()
                signatures.append(signature)
            layer_keys = [
                [execution["algorithm"].id, execution["kwargs"]["feedstock_id"]]
                for execution in execution_plan
            ]
            callback = finalize_inventory.s(scenario_id, str(run_id), layer_keys)
            callback.on_error(mark_inventory_failed.si(scenario_id, str(run_id)))
            callback_id = callback.freeze().id
            task_chord = chord(signatures, callback)
            RunningTask.objects.bulk_create(
                [
                    *(
                        RunningTask(
                            scenario_id=scenario_id,
                            uuid=signature.id,
                            algorithm=execution["algorithm"],
                            run_id=run_id,
                        )
                        for signature, execution in zip(
                            signatures, execution_plan, strict=True
                        )
                    ),
                    RunningTask(
                        scenario_id=scenario_id, uuid=callback_id, run_id=run_id
                    ),
                ]
            )
            transaction.on_commit(partial(task_chord.apply_async, task_id=callback_id))
    except Exception as error:
        mark_inventory_failed.run(scenario_id, run_id, failure_message=str(error))
        raise
    return [signature.id for signature in signatures]


class InventoryAlgorithmTask(app.Task):
    """Terminal-state reconciliation trigger for algorithm task completions."""

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        super().after_return(status, retval, task_id, args, kwargs, einfo)
        if status in READY_STATES:
            kwargs = kwargs or {}
            scenario_id = kwargs.get("scenario_id")
            run_id = kwargs.get("run_id")
            if scenario_id and run_id:
                _safe_enqueue_settlement(scenario_id, run_id)


@app.task(bind=True, base=InventoryAlgorithmTask)
def run_inventory_algorithm(self, algorithm_id, *, scenario_id, run_id, **kwargs):
    algorithm = None
    try:
        with locked_scenario_evaluation(scenario_id) as locked:
            if locked is None:
                return None
            _, scenario_status, _ = locked
            if not is_current_inventory_run(scenario_status, run_id) or (
                scenario_status.status != ScenarioStatus.Status.RUNNING
            ):
                return None
            algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
        results = algorithm.execute(scenario_id=scenario_id, **kwargs)
        with locked_scenario_evaluation(scenario_id) as locked:
            if locked is None:
                return None
            scenario, scenario_status, _ = locked
            if not is_current_inventory_run(scenario_status, run_id) or (
                scenario_status.status != ScenarioStatus.Status.RUNNING
            ):
                return None
            Layer.objects.create_or_replace(
                staged=True,
                name=algorithm.function_name,
                scenario=scenario,
                feedstock=Material.objects.get(id=kwargs["feedstock_id"]),
                sample_series=SampleSeries.objects.filter(
                    id=kwargs.get("sample_series_id")
                ).first(),
                algorithm=algorithm,
                results=results,
                run_id=scenario_status.run_id,
            )
    except Exception as error:
        mark_inventory_failed.run(
            scenario_id,
            run_id,
            algorithm.pk if algorithm is not None else None,
            str(error),
        )
        raise
    return True


@app.task
def finalize_inventory(results, scenario_id, run_id, layer_keys=None):
    with locked_scenario_evaluation(scenario_id) as locked:
        if locked is None:
            return
        _, scenario_status, _ = locked
        # Only a matched RUNNING generation may finalize; stale/FAILED/finished
        # attempts no-op before the results are even validated.
        if not is_current_inventory_run(scenario_status, run_id) or (
            scenario_status.status != ScenarioStatus.Status.RUNNING
        ):
            return
        if not all(results):
            raise RuntimeError("Inventory algorithm did not complete.")
        RunningTask.objects.filter(
            scenario_id=scenario_id, run_id=scenario_status.run_id
        ).delete()
        current_layers = (
            None if layer_keys is None else {tuple(key) for key in layer_keys}
        )
        for layer in Layer.all_objects.filter(
            scenario_id=scenario_id, staged=True, run_id=scenario_status.run_id
        ):
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


@app.task(
    autoretry_for=(OperationalError,),
    retry_kwargs={"max_retries": 3},
    default_retry_delay=2,
)
def settle_failed_inventory_run(scenario_id, run_id):
    """Reconcile one failed generation once its task rows are all terminal.

    Deletes only that run's markers and staged layers; keeps the FAILED
    diagnostics and every prior live output. Idempotent; a stale or missing
    run_id is a no-op.
    """
    with locked_scenario_evaluation(scenario_id) as locked:
        if locked is None:
            return
        _, scenario_status, _ = locked
        if not is_current_inventory_run(scenario_status, run_id) or (
            scenario_status.status != ScenarioStatus.Status.FAILED
        ):
            return
        run_tasks = list(
            RunningTask.objects.filter(scenario_id=scenario_id, run_id=run_id)
        )
        if not _header_tasks_ready(run_tasks, run_id):
            return
        RunningTask.objects.filter(id__in=[task.id for task in run_tasks]).delete()
        for layer in Layer.all_objects.filter(
            scenario_id=scenario_id, staged=True, run_id=run_id
        ):
            layer.delete()
