from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from maps.models import GeoDataset, Region
from materials.models import Material, SampleSeries

from ..models import InventoryAlgorithm, RunningTask, Scenario, ScenarioStatus
from ..tasks import mark_inventory_failed, run_inventory, run_inventory_algorithm


class InventoryTaskFailureTests(TestCase):
    def test_mark_inventory_failed_sets_failed_and_clears_running_tasks(self):
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
        self.assertFalse(RunningTask.objects.filter(scenario=scenario).exists())

    @patch("inventories.tasks.chord")
    @patch("inventories.tasks.mark_inventory_failed")
    @patch("inventories.tasks.finalize_inventory")
    @patch("inventories.tasks.Scenario")
    def test_run_inventory_attaches_failure_errback(
        self,
        scenario_model,
        finalize_inventory_task,
        mark_inventory_failed_task,
        chord_factory,
    ):
        scenario = Mock(id=17)
        scenario.inventory_execution_plan.return_value = []
        scenario_model.objects.get.return_value = scenario
        callback = Mock()
        finalize_inventory_task.s.return_value = callback
        errback = Mock()
        mark_inventory_failed_task.si.return_value = errback
        task_chord = Mock(tasks=[])
        chord_factory.return_value = task_chord

        run_inventory.run(scenario.id)

        callback.on_error.assert_called_once_with(errback)

    @patch("inventories.tasks.mark_inventory_failed")
    @patch("inventories.tasks.Scenario")
    def test_run_inventory_marks_failed_when_setup_raises(
        self,
        scenario_model,
        mark_inventory_failed_task,
    ):
        scenario = Mock(id=23)
        scenario.delete_result_layers.side_effect = RuntimeError("setup failed")
        scenario_model.objects.get.return_value = scenario

        with self.assertRaisesMessage(RuntimeError, "setup failed"):
            run_inventory.run(scenario.id)

        mark_inventory_failed_task.run.assert_called_once_with(
            scenario.id,
            failure_message="setup failed",
        )

    @patch("inventories.tasks.InventoryAlgorithm.execute")
    def test_algorithm_failure_records_algorithm_and_cleans_running_tasks(
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
        feedstock = SampleSeries.objects.create(
            name="Algorithm Failure Feedstock",
            material=Material.objects.create(name="Algorithm Failure Material"),
        )
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
        self.assertFalse(RunningTask.objects.filter(scenario=scenario).exists())

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
        feedstock = SampleSeries.objects.create(
            name="Persistence Failure Feedstock",
            material=Material.objects.create(name="Persistence Failure Material"),
        )
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
        self.assertFalse(RunningTask.objects.filter(scenario=scenario).exists())
