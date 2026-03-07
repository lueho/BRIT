from django.test import TestCase

from maps.models import Region

from ..exceptions import BlockedRunningScenario
from ..models import (
    GeoDataset,
    InventoryAlgorithm,
    Material,
    RunningTask,
    Scenario,
    ScenarioStatus,
)
from uuid import uuid4
from unittest.mock import patch


class ScenarioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        feedstock1 = Material.objects.create(name="Feedstock 1")
        Material.objects.create(name="Feedstock 2")
        region = Region.objects.create(name="Test Region")
        cls.scenario = Scenario.objects.create(name="Test Scenario", region=region)

        geodataset = GeoDataset.objects.create(name="Test Dataset", region=region)
        algorithm = InventoryAlgorithm.objects.create(
            name="Test Algorithm", geodataset=geodataset
        )
        algorithm.feedstocks.add(feedstock1)

    def setUp(self):
        self.scenario.refresh_from_db()

    def test_available_geodatasets_with_single_feedstock(self):
        feedstock = Material.objects.get(name="Feedstock 1")
        geodatasets = self.scenario.available_geodatasets(feedstock=feedstock)
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_geodatasets_with_feedstock_queryset(self):
        feedstocks = Material.objects.all()
        geodatasets = self.scenario.available_geodatasets(feedstocks=feedstocks)
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_geodatasets_with_missing_input(self):
        geodatasets = self.scenario.available_geodatasets()
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_inventory_algorithms_with_single_feedstock(self):
        feedstock = Material.objects.get(name="Feedstock 1")
        algorithms = self.scenario.available_inventory_algorithms(feedstock=feedstock)
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )

    def test_available_inventory_algorithms_with_feedstock_queryset(self):
        feedstocks = Material.objects.all()
        algorithms = self.scenario.available_inventory_algorithms(feedstocks=feedstocks)
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )

    def test_available_inventory_algorithms_with_missing_input(self):
        algorithms = self.scenario.available_inventory_algorithms()
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )

    def test_inventory_algorithm_task_reference_round_trip(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="Resolver Algorithm",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=GeoDataset.objects.get(name="Test Dataset"),
        )

        self.assertEqual(
            algorithm.module_path,
            "case_studies.flexibi_hamburg.algorithms",
        )
        self.assertEqual(
            algorithm.task_reference,
            "case_studies.flexibi_hamburg.algorithms:hamburg_roadside_tree_production",
        )
        self.assertEqual(
            InventoryAlgorithm.parse_task_reference(algorithm.task_reference),
            ("flexibi_hamburg", "hamburg_roadside_tree_production"),
        )
        self.assertEqual(
            InventoryAlgorithm.from_task_reference(algorithm.task_reference),
            algorithm,
        )

    @patch("inventories.models.AsyncResult")
    def test_running_scenario_save_stays_blocked_while_task_is_active(
        self, mock_async_result
    ):
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(scenario=self.scenario, uuid=uuid4())
        mock_async_result.return_value.state = "STARTED"
        self.scenario.name = "Updated While Running"

        with self.assertRaises(BlockedRunningScenario):
            self.scenario.save()

    @patch("inventories.models.AsyncResult")
    def test_running_scenario_save_recovers_after_failed_tasks(self, mock_async_result):
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        running_task = RunningTask.objects.create(scenario=self.scenario, uuid=uuid4())
        mock_async_result.return_value.state = "FAILURE"
        self.scenario.name = "Recovered After Failure"

        self.scenario.save()
        self.scenario.refresh_from_db()

        self.assertEqual(self.scenario.name, "Recovered After Failure")
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertFalse(RunningTask.objects.filter(id=running_task.id).exists())
