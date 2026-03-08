from django.test import TestCase

from maps.models import Region
from materials.models import SampleSeries

from ..exceptions import BlockedRunningScenario
from ..models import (
    GeoDataset,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Material,
    RunningTask,
    Scenario,
    ScenarioConfigurationError,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
)
from uuid import uuid4
from unittest.mock import Mock, patch


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

    def test_inventory_algorithm_execute_uses_resolved_callable(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="Resolver Algorithm",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=GeoDataset.objects.get(name="Test Dataset"),
        )
        execute = Mock(return_value={"result": "ok"})
        module = type(
            "FakeModule",
            (),
            {
                "InventoryAlgorithms": type(
                    "FakeInventoryAlgorithms",
                    (),
                    {"hamburg_roadside_tree_production": staticmethod(execute)},
                )
            },
        )

        with patch.object(algorithm, "import_module", return_value=module):
            result = algorithm.execute(example="value")

        self.assertEqual(result, {"result": "ok"})
        execute.assert_called_once_with(example="value")

    def test_serialize_inventory_execution_plan_builds_legacy_task_reference_shape(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="Resolver Algorithm",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=GeoDataset.objects.get(name="Test Dataset"),
        )
        execution_plan = [
            {
                "algorithm": algorithm,
                "kwargs": {
                    "catchment_id": 11,
                    "scenario_id": self.scenario.id,
                    "feedstock_id": 7,
                    "point_yield": {"value": 1.0, "standard_deviation": 0.1},
                },
            }
        ]

        config = self.scenario.serialize_inventory_execution_plan(execution_plan)

        self.assertEqual(
            config,
            {
                7: {
                    algorithm.task_reference: {
                        "catchment_id": 11,
                        "scenario_id": self.scenario.id,
                        "feedstock_id": 7,
                        "point_yield": {"value": 1.0, "standard_deviation": 0.1},
                    }
                }
            },
        )
        self.assertIsNot(config[7][algorithm.task_reference], execution_plan[0]["kwargs"])

    def test_is_valid_configuration_scopes_required_parameters_to_current_scenario(self):
        material = Material.objects.get(name="Feedstock 1")
        feedstock = SampleSeries.objects.create(
            material=material,
            name="Feedstock 1 Series",
        )
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.create(
            name="Scoped Validation Algorithm",
            geodataset=geodataset,
        )
        algorithm.feedstocks.add(material)
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Point yield",
            short_name="point_yield",
            is_required=True,
        )
        parameter.inventory_algorithm.add(algorithm)
        value = InventoryAlgorithmParameterValue.objects.create(
            name="Default point yield",
            parameter=parameter,
            value=1.0,
            standard_deviation=0.0,
            default=True,
        )

        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
        )

        other_scenario = Scenario.objects.create(
            name="Other Scenario",
            region=self.scenario.region,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=other_scenario,
            feedstock=feedstock,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=value,
        )

        with self.assertRaises(ScenarioConfigurationError):
            self.scenario.is_valid_configuration()

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
