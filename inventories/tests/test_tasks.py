from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from layer_manager.models import Layer
from maps.models import GeoDataset, Region
from materials.models import Material

from ..models import InventoryAlgorithm, RunningTask, Scenario, ScenarioStatus
from ..tasks import (
    finalize_inventory,
    mark_inventory_failed,
    run_inventory,
    run_inventory_algorithm,
    start_inventory_run,
)


class InventoryTaskFailureTests(TestCase):
    def test_mark_inventory_failed_sets_failed_and_keeps_running_tasks(self):
        scenario = Scenario.objects.create(
            name="Failed Scenario",
            region=Region.objects.create(name="Failure Region"),
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Failed Algorithm",
            geodataset=GeoDataset.objects.create(
                name="Failure Dataset",
                region=scenario.region,
            ),
        )
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(
            scenario=scenario,
            algorithm=algorithm,
            uuid=uuid4(),
        )

        mark_inventory_failed.run(scenario.pk, algorithm.pk, "calculation failed")

        scenario.scenariostatus.refresh_from_db()
        self.assertEqual(scenario.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario.scenariostatus.failed_algorithm, algorithm)
        self.assertEqual(
            scenario.scenariostatus.failure_message,
            "calculation failed",
        )
        self.assertTrue(RunningTask.objects.filter(scenario=scenario).exists())

    @patch("inventories.tasks.InventoryAlgorithm.execute")
    def test_algorithm_failure_records_algorithm_and_keeps_running_tasks(
        self,
        execute_algorithm,
    ):
        execute_algorithm.side_effect = RuntimeError("calculation failed")
        region = Region.objects.create(name="Algorithm Failure Region")
        scenario = Scenario.objects.create(
            name="Algorithm Failure Scenario",
            region=region,
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Algorithm Failure",
            geodataset=GeoDataset.objects.create(
                name="Algorithm Failure Dataset",
                region=region,
            ),
        )
        feedstock = Material.objects.create(name="Algorithm Failure Material")
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(
            scenario=scenario,
            algorithm=algorithm,
            uuid=uuid4(),
        )

        with self.assertRaisesMessage(RuntimeError, "calculation failed"):
            run_inventory_algorithm.run(
                algorithm.pk,
                scenario_id=scenario.pk,
                feedstock_id=feedstock.pk,
            )

        scenario.scenariostatus.refresh_from_db()
        self.assertEqual(scenario.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario.scenariostatus.failed_algorithm, algorithm)
        self.assertEqual(
            scenario.scenariostatus.failure_message,
            "calculation failed",
        )
        self.assertTrue(RunningTask.objects.filter(scenario=scenario).exists())

    @patch("inventories.tasks.Layer.objects.create_or_replace")
    @patch("inventories.tasks.InventoryAlgorithm.execute")
    def test_result_persistence_failure_records_algorithm(
        self,
        execute_algorithm,
        create_result_layer,
    ):
        execute_algorithm.return_value = {"result": 1}
        create_result_layer.side_effect = RuntimeError("result persistence failed")
        region = Region.objects.create(name="Persistence Failure Region")
        scenario = Scenario.objects.create(
            name="Persistence Failure Scenario",
            region=region,
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Persistence Failure",
            function_name="persistence_failure",
            geodataset=GeoDataset.objects.create(
                name="Persistence Failure Dataset",
                region=region,
            ),
        )
        feedstock = Material.objects.create(name="Persistence Failure Material")
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(
            scenario=scenario,
            algorithm=algorithm,
            uuid=uuid4(),
        )

        with self.assertRaisesMessage(RuntimeError, "result persistence failed"):
            run_inventory_algorithm.run(
                algorithm.pk,
                scenario_id=scenario.pk,
                feedstock_id=feedstock.pk,
            )

        scenario.scenariostatus.refresh_from_db()
        self.assertEqual(scenario.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario.scenariostatus.failed_algorithm, algorithm)
        self.assertEqual(
            scenario.scenariostatus.failure_message,
            "result persistence failed",
        )
        self.assertTrue(RunningTask.objects.filter(scenario=scenario).exists())


class InventoryRunSerializationTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Serialization Region")
        self.scenario = Scenario.objects.create(
            name="Serialization Scenario",
            region=self.region,
        )
        self.geodataset = GeoDataset.objects.create(
            name="Serialization Dataset",
            region=self.region,
        )
        self.algorithm = InventoryAlgorithm.objects.create(
            name="Serialization Algorithm",
            function_name="serialization_algorithm",
            geodataset=self.geodataset,
        )
        self.other_algorithm = InventoryAlgorithm.objects.create(
            name="Removed Algorithm",
            function_name="removed_algorithm",
            geodataset=self.geodataset,
        )
        self.feedstock = Material.objects.create(name="Serialization Material")

    def create_layer(self, algorithm, staged=False):
        return Layer.all_objects.create(
            name=algorithm.function_name,
            geom_type="Polygon",
            table_name=(
                f"result_of_scenario_{self.scenario.pk}"
                f"_algorithm_{algorithm.pk}_feedstock_{self.feedstock.pk}"
                f"{'_alt' if staged else ''}"
            ),
            scenario=self.scenario,
            feedstock=self.feedstock,
            algorithm=algorithm,
            staged=staged,
        )

    def execution_plan(self):
        return [
            {
                "algorithm": self.algorithm,
                "kwargs": {
                    "scenario_id": self.scenario.pk,
                    "feedstock_id": self.feedstock.pk,
                },
            }
        ]

    def create_running_task(self):
        return RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid4(),
        )

    @patch("inventories.tasks.chord")
    def test_run_inventory_keeps_prior_result_layers(self, chord_factory):
        chord_factory.return_value = Mock()
        layer = self.create_layer(self.algorithm)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with patch.object(
            Scenario, "inventory_execution_plan", return_value=self.execution_plan()
        ):
            run_inventory.run(self.scenario.pk)

        self.assertTrue(Layer.objects.filter(pk=layer.pk).exists())

    @patch("inventories.tasks.chord")
    def test_failed_run_setup_keeps_prior_result_layers(self, chord_factory):
        layer = self.create_layer(self.algorithm)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with (
            patch.object(
                Scenario,
                "inventory_execution_plan",
                side_effect=RuntimeError("setup failed"),
            ),
            self.assertRaisesMessage(RuntimeError, "setup failed"),
        ):
            run_inventory.run(self.scenario.pk)

        chord_factory.assert_not_called()
        self.assertTrue(Layer.objects.filter(pk=layer.pk).exists())
        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(self.scenario.scenariostatus.failure_message, "setup failed")

    @patch("inventories.tasks.mark_inventory_failed")
    @patch("inventories.tasks.chord")
    def test_run_inventory_attaches_failure_errback(
        self, chord_factory, mark_inventory_failed_task
    ):
        chord_factory.return_value = Mock()
        errback = Mock()
        mark_inventory_failed_task.si.return_value = errback
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with (
            patch.object(
                Scenario,
                "inventory_execution_plan",
                return_value=self.execution_plan(),
            ),
            patch("inventories.tasks.finalize_inventory") as finalize_task,
        ):
            callback = Mock()
            callback.freeze.return_value.id = str(uuid4())
            finalize_task.s.return_value = callback
            run_inventory.run(self.scenario.pk)

        finalize_task.s.assert_called_once_with(
            self.scenario.pk, [[self.algorithm.pk, self.feedstock.pk]]
        )
        callback.on_error.assert_called_once_with(errback)

    @patch("inventories.tasks.chord")
    def test_run_inventory_records_tasks_before_dispatch_on_commit(self, chord_factory):
        task_chord = Mock()
        chord_factory.return_value = task_chord
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with (
            patch.object(
                Scenario,
                "inventory_execution_plan",
                return_value=self.execution_plan(),
            ),
            self.captureOnCommitCallbacks(execute=False) as callbacks,
        ):
            run_inventory.run(self.scenario.pk)

        signatures = chord_factory.call_args.args[0]
        callback_id = chord_factory.call_args.args[1].id
        self.assertCountEqual(
            [
                (str(uuid), algorithm_id)
                for uuid, algorithm_id in RunningTask.objects.filter(
                    scenario=self.scenario
                ).values_list("uuid", "algorithm_id")
            ],
            [(signatures[0].id, self.algorithm.pk), (callback_id, None)],
        )
        task_chord.apply_async.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        task_chord.apply_async.assert_called_once_with(task_id=callback_id)

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.chord")
    def test_run_inventory_skips_duplicate_while_run_is_active(
        self, chord_factory, async_result
    ):
        async_result.return_value.state = "STARTED"
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        running_task = self.create_running_task()

        with patch.object(
            Scenario, "inventory_execution_plan", return_value=self.execution_plan()
        ):
            run_inventory.run(self.scenario.pk)

        chord_factory.assert_not_called()
        self.assertEqual(
            list(RunningTask.objects.filter(scenario=self.scenario)), [running_task]
        )

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.chord")
    def test_run_inventory_replaces_stale_running_tasks(
        self, chord_factory, async_result
    ):
        async_result.return_value.state = "SUCCESS"
        chord_factory.return_value = Mock()
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        stale_task = self.create_running_task()

        with patch.object(
            Scenario, "inventory_execution_plan", return_value=self.execution_plan()
        ):
            run_inventory.run(self.scenario.pk)

        chord_factory.assert_called_once()
        running_tasks = RunningTask.objects.filter(
            scenario=self.scenario, algorithm__isnull=False
        )
        self.assertEqual(running_tasks.count(), 1)
        self.assertFalse(RunningTask.objects.filter(pk=stale_task.pk).exists())
        self.assertNotEqual(running_tasks.get().uuid, stale_task.uuid)

    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_claims_scenario_and_dispatches_on_commit(
        self, run_inventory_task
    ):
        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertTrue(started)
        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.RUNNING)
        run_inventory_task.delay.assert_called_once_with(self.scenario.pk)

    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_rejects_pending_run(self, run_inventory_task):
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertFalse(started)
        run_inventory_task.delay.assert_not_called()

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_rejects_active_run(
        self, run_inventory_task, async_result
    ):
        async_result.return_value.state = "STARTED"
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        self.create_running_task()

        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertFalse(started)
        run_inventory_task.delay.assert_not_called()

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_rejects_failed_run_with_active_siblings(
        self, run_inventory_task, async_result
    ):
        async_result.return_value.state = "STARTED"
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        self.create_running_task()
        mark_inventory_failed.run(self.scenario.pk, self.algorithm.pk, "failed")

        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertFalse(started)
        run_inventory_task.delay.assert_not_called()

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_restarts_stale_run(
        self, run_inventory_task, async_result
    ):
        async_result.return_value.state = "FAILURE"
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        self.create_running_task()

        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertTrue(started)
        run_inventory_task.delay.assert_called_once_with(self.scenario.pk)

    @patch("inventories.tasks.AsyncResult")
    @patch("inventories.tasks.run_inventory")
    def test_start_inventory_run_forgets_finished_tasks_of_the_earlier_run(
        self, run_inventory_task, async_result
    ):
        async_result.return_value.state = "FAILURE"
        mark_inventory_failed.run(self.scenario.pk, self.algorithm.pk, "failed")
        self.create_running_task()

        with self.captureOnCommitCallbacks(execute=True):
            started = start_inventory_run(self.scenario.pk)

        self.assertTrue(started)
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertFalse(start_inventory_run(self.scenario.pk))
        run_inventory_task.delay.assert_called_once_with(self.scenario.pk)

    @patch("inventories.tasks.Layer.delete", autospec=True)
    def test_finalize_inventory_prunes_only_layers_outside_the_run(self, delete_layer):
        kept_layer = self.create_layer(self.algorithm)
        stale_layer = self.create_layer(self.other_algorithm)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        self.create_running_task()

        finalize_inventory.run(
            [True],
            self.scenario.pk,
            [[self.algorithm.pk, self.feedstock.pk]],
        )

        delete_layer.assert_called_once_with(stale_layer)
        self.assertNotIn(kept_layer, [c.args[0] for c in delete_layer.call_args_list])
        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())

    @patch("inventories.tasks.Layer.delete", autospec=True)
    def test_failed_finalize_keeps_all_layers(self, delete_layer):
        self.create_layer(self.other_algorithm)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with self.assertRaises(RuntimeError):
            finalize_inventory.run(
                [True, False],
                self.scenario.pk,
                [[self.algorithm.pk, self.feedstock.pk]],
            )

        delete_layer.assert_not_called()

    @patch("inventories.tasks.Layer.objects.create_or_replace")
    @patch("inventories.tasks.InventoryAlgorithm.execute")
    def test_run_inventory_algorithm_stages_its_result(
        self, execute_algorithm, create_result_layer
    ):
        execute_algorithm.return_value = {"features": []}

        run_inventory_algorithm.run(
            self.algorithm.pk,
            scenario_id=self.scenario.pk,
            feedstock_id=self.feedstock.pk,
        )

        self.assertTrue(create_result_layer.call_args.kwargs["staged"])

    @patch("inventories.tasks.chord")
    @patch("inventories.tasks.Layer.delete", autospec=True)
    def test_run_inventory_discards_leftover_staged_layers(
        self, delete_layer, chord_factory
    ):
        chord_factory.return_value = Mock()
        live_layer = self.create_layer(self.algorithm)
        leftover_layer = self.create_layer(self.algorithm, staged=True)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with patch.object(
            Scenario, "inventory_execution_plan", return_value=self.execution_plan()
        ):
            run_inventory.run(self.scenario.pk)

        delete_layer.assert_called_once_with(leftover_layer)
        self.assertTrue(Layer.objects.filter(pk=live_layer.pk).exists())

    @patch("inventories.tasks.Layer.delete", autospec=True)
    def test_finalize_inventory_publishes_staged_layers(self, delete_layer):
        previous_layer = self.create_layer(self.algorithm)
        staged_layer = self.create_layer(self.algorithm, staged=True)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        finalize_inventory.run(
            [True],
            self.scenario.pk,
            [[self.algorithm.pk, self.feedstock.pk]],
        )

        delete_layer.assert_called_once_with(previous_layer)
        staged_layer.refresh_from_db()
        self.assertFalse(staged_layer.staged)
        self.assertIn(staged_layer, self.scenario.layer_set.all())

    @patch("inventories.tasks.Layer.delete", autospec=True)
    def test_failed_finalize_keeps_previous_results_and_hides_staged(
        self, delete_layer
    ):
        previous_layer = self.create_layer(self.algorithm)
        staged_layer = self.create_layer(self.algorithm, staged=True)
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with self.assertRaises(RuntimeError):
            finalize_inventory.run(
                [True, False],
                self.scenario.pk,
                [[self.algorithm.pk, self.feedstock.pk]],
            )

        delete_layer.assert_not_called()
        staged_layer.refresh_from_db()
        self.assertTrue(staged_layer.staged)
        self.assertEqual(list(self.scenario.layer_set.all()), [previous_layer])
