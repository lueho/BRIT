import importlib
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.exceptions import IrreversibleError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from distributions.models import TemporalDistribution, Timestep
from layer_manager.models import Layer, LayerAggregatedDistribution
from maps.models import Catchment, Region
from materials.models import Sample, SampleSeries
from sources.greenhouses.inventory.algorithms import (
    InventoryAlgorithms as GreenhouseInventoryAlgorithms,
)

from ..evaluations import ScenarioResult
from ..exceptions import BlockedRunningScenario
from ..models import (
    FeedstockNotImplemented,
    GeoDataset,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    InventoryAmountShare,
    InventoryInput,
    Material,
    RunningTask,
    Scenario,
    ScenarioConfigurationError,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
)


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

    def set_failed_status(self, algorithm):
        scenario_status = self.scenario.scenariostatus
        scenario_status.status = ScenarioStatus.Status.FAILED
        scenario_status.failed_algorithm = algorithm
        scenario_status.failure_message = "calculation failed"
        scenario_status.save()

    def test_scenario_edit_clears_failure_metadata(self):
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        self.set_failed_status(algorithm)

        self.scenario.name = "Updated Scenario"
        self.scenario.save()

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(self.scenario.scenariostatus.failed_algorithm)
        self.assertEqual(self.scenario.scenariostatus.failure_message, "")

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

    def test_greenhouse_inventory_algorithms_are_owned_by_sources(self):
        self.assertEqual(
            GreenhouseInventoryAlgorithms.__module__,
            "sources.greenhouses.inventory.algorithms",
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
            "sources.roadside_trees.inventory.algorithms",
        )
        self.assertEqual(
            algorithm.task_reference,
            "sources.roadside_trees.inventory.algorithms:hamburg_roadside_tree_production",
        )
        self.assertEqual(
            InventoryAlgorithm.parse_task_reference(algorithm.task_reference),
            (
                "sources.roadside_trees.inventory.algorithms",
                "hamburg_roadside_tree_production",
            ),
        )
        self.assertEqual(
            InventoryAlgorithm.from_task_reference(algorithm.task_reference),
            algorithm,
        )

    def test_inventory_algorithm_from_task_reference_supports_legacy_case_studies_paths(
        self,
    ):
        algorithm = InventoryAlgorithm.objects.create(
            name="Resolver Algorithm",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=GeoDataset.objects.get(name="Test Dataset"),
        )

        legacy_task_reference = (
            "case_studies.flexibi_hamburg.algorithms:hamburg_roadside_tree_production"
        )

        self.assertEqual(
            InventoryAlgorithm.parse_task_reference(legacy_task_reference),
            ("flexibi_hamburg", "hamburg_roadside_tree_production"),
        )
        self.assertEqual(
            InventoryAlgorithm.from_task_reference(legacy_task_reference),
            algorithm,
        )

    def test_inventory_algorithm_task_reference_supports_fully_qualified_module_path(
        self,
    ):
        algorithm = InventoryAlgorithm.objects.create(
            name="Resolver Algorithm",
            source_module="sources.roadside_trees.inventory.algorithms",
            function_name="roadside_tree_production",
            geodataset=GeoDataset.objects.get(name="Test Dataset"),
        )

        self.assertEqual(
            algorithm.module_path,
            "sources.roadside_trees.inventory.algorithms",
        )
        self.assertEqual(
            algorithm.task_reference,
            "sources.roadside_trees.inventory.algorithms:roadside_tree_production",
        )
        self.assertEqual(
            InventoryAlgorithm.parse_task_reference(algorithm.task_reference),
            (
                "sources.roadside_trees.inventory.algorithms",
                "roadside_tree_production",
            ),
        )
        self.assertEqual(
            InventoryAlgorithm.from_task_reference(algorithm.task_reference),
            algorithm,
        )

    @patch("inventories.models.importlib.import_module")
    @patch("inventories.models.pkgutil.iter_modules")
    def test_available_modules_includes_nested_sources_inventory_modules(
        self, mock_iter_modules, mock_import_module
    ):
        mock_iter_modules.return_value = [
            SimpleNamespace(name="greenhouses", ispkg=True),
            SimpleNamespace(name="tests", ispkg=True),
            SimpleNamespace(name="views", ispkg=False),
        ]

        def import_module_side_effect(module_path):
            if module_path == "sources.greenhouses.inventory.algorithms":
                return SimpleNamespace(InventoryAlgorithms=object())
            if module_path == "sources.tests.inventory.algorithms":
                raise ModuleNotFoundError(name="sources.tests.inventory")
            raise AssertionError(f"Unexpected import attempt: {module_path}")

        mock_import_module.side_effect = import_module_side_effect

        self.assertEqual(
            InventoryAlgorithm.available_modules(),
            [
                "flexibi_hamburg",
                "sources.greenhouses.inventory.algorithms",
            ],
        )
        mock_iter_modules.assert_called_once()

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

    def test_serialize_inventory_execution_plan_builds_sources_task_reference_shape(
        self,
    ):
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
                    "inventory_input_id": 7,
                    "feedstock_id": 3,
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
                        "inventory_input_id": 7,
                        "feedstock_id": 3,
                        "point_yield": {"value": 1.0, "standard_deviation": 0.1},
                    }
                }
            },
        )
        self.assertIsNot(
            config[7][algorithm.task_reference], execution_plan[0]["kwargs"]
        )

    def test_serialize_inventory_execution_plan_falls_back_to_feedstock_id(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="Legacy Plan Algorithm",
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
                },
            }
        ]

        config = self.scenario.serialize_inventory_execution_plan(execution_plan)

        self.assertIn(7, config)
        self.assertIn(algorithm.task_reference, config[7])

    def test_is_valid_configuration_scopes_required_parameters_to_current_scenario(
        self,
    ):
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
            feedstock=feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
        )

        other_scenario = Scenario.objects.create(
            name="Other Scenario",
            region=self.scenario.region,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=other_scenario,
            feedstock=feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=value,
        )

        with self.assertRaises(ScenarioConfigurationError):
            self.scenario.is_valid_configuration()

    def test_inventory_algorithm_config_is_scoped_to_feedstock_and_uses_short_names(
        self,
    ):
        material = Material.objects.get(name="Feedstock 1")
        other_material = Material.objects.get(name="Feedstock 2")
        feedstock = SampleSeries.objects.create(
            material=material,
            name="Feedstock 1 Series",
        )
        other_feedstock = SampleSeries.objects.create(
            material=other_material,
            name="Feedstock 2 Series",
        )
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.create(
            name="Scoped Config Algorithm",
            geodataset=geodataset,
        )
        algorithm.feedstocks.add(material, other_material)
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Point yield",
            short_name="point_yield",
            is_required=True,
        )
        parameter.inventory_algorithm.add(algorithm)
        value = InventoryAlgorithmParameterValue.objects.create(
            name="Feedstock 1 Value",
            parameter=parameter,
            value=1.0,
            standard_deviation=0.1,
            default=True,
        )
        other_value = InventoryAlgorithmParameterValue.objects.create(
            name="Feedstock 2 Value",
            parameter=parameter,
            value=2.0,
            standard_deviation=0.2,
            default=False,
        )

        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=value,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=other_feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=other_value,
        )

        config = self.scenario.inventory_algorithm_config(
            algorithm, feedstock.inventory_input
        )

        self.assertEqual(config["scenario"], self.scenario)
        self.assertEqual(config["feedstock"], feedstock.inventory_input)
        self.assertEqual(config["geodataset"], geodataset)
        self.assertEqual(config["inventory_algorithm"], algorithm)
        self.assertEqual(config["parameters"], [{"point_yield": value.id}])

    def test_add_inventory_algorithm_creates_config_rows_atomically(self):
        """add_inventory_algorithm must create all config rows inside transaction.atomic."""
        material = Material.objects.get(name="Feedstock 1")
        feedstock = SampleSeries.objects.create(
            material=material, name="Atomic Feedstock Series"
        )
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.create(
            name="Atomic Test Algorithm", geodataset=geodataset
        )
        algorithm.feedstocks.add(material)
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Atomic Param", short_name="atomic_param"
        )
        parameter.inventory_algorithm.add(algorithm)
        InventoryAlgorithmParameterValue.objects.create(
            name="Val 1", parameter=parameter, value=1.0, default=True
        )
        InventoryAlgorithmParameterValue.objects.create(
            name="Val 2", parameter=parameter, value=2.0, default=False
        )

        self.scenario.add_inventory_algorithm(feedstock, algorithm)

        configs = ScenarioInventoryConfiguration.objects.filter(
            scenario=self.scenario,
            inventory_algorithm=algorithm,
            feedstock=feedstock.inventory_input,
        )
        self.assertTrue(configs.exists())

    def test_scenario_status_updates_when_referenced_parameter_value_changes(self):
        """#212: Changing a referenced InventoryAlgorithmParameterValue must
        mark all scenarios that use it as CHANGED."""
        material = Material.objects.get(name="Feedstock 1")
        feedstock = SampleSeries.objects.create(
            name="FK Signal Series", material=material
        )
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Signal Param", short_name="signal_param"
        )
        parameter.inventory_algorithm.add(algorithm)
        value = InventoryAlgorithmParameterValue.objects.create(
            name="Signal Value",
            parameter=parameter,
            value=1.0,
            standard_deviation=0.0,
            default=True,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=value,
        )
        # Creating the config set status to CHANGED; set it to FINISHED
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)
        self.set_failed_status(algorithm)

        # Modify the referenced parameter value
        value.value = 2.0
        value.save()

        # Scenario status should now be CHANGED
        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(self.scenario.scenariostatus.failed_algorithm)
        self.assertEqual(self.scenario.scenariostatus.failure_message, "")

    def test_scenario_status_updates_when_referenced_algorithm_changes(self):
        """#212: Changing a referenced InventoryAlgorithm must mark all
        scenarios that use it as CHANGED."""
        material = Material.objects.get(name="Feedstock 1")
        feedstock = SampleSeries.objects.create(
            name="FK Algo Series", material=material
        )
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock.inventory_input,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
        )
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)
        self.set_failed_status(algorithm)

        # Modify the referenced algorithm
        algorithm.name = "Updated Algorithm"
        algorithm.save()

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(self.scenario.scenariostatus.failed_algorithm)
        self.assertEqual(self.scenario.scenariostatus.failure_message, "")

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
    def test_running_scenario_guard_locks_status_and_tasks(self, mock_async_result):
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(scenario=self.scenario, uuid=uuid4())
        mock_async_result.return_value.state = "STARTED"
        self.scenario.name = "Updated While Running"

        with CaptureQueriesContext(connection) as queries:
            with self.assertRaises(BlockedRunningScenario):
                self.scenario.save()

        locking_queries = [
            query["sql"]
            for query in queries.captured_queries
            if "FOR UPDATE" in query["sql"]
        ]
        self.assertTrue(
            any("inventories_scenariostatus" in query for query in locking_queries)
        )
        self.assertTrue(
            any("inventories_runningtask" in query for query in locking_queries)
        )

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

    def test_create_default_configuration_handles_m2m_parameter_algorithms(self):
        """#219: create_default_configuration() must create one entry per
        parameter and feedstock series even though
        InventoryAlgorithmParameter.inventory_algorithm is a ManyToManyField."""
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        algorithm.default = True
        algorithm.save()
        feedstock = SampleSeries.objects.create(
            material=Material.objects.get(name="Feedstock 1"),
            name="Default Feedstock Series",
        )

        parameter = InventoryAlgorithmParameter.objects.create(
            short_name="test_param",
            is_required=True,
        )
        parameter.inventory_algorithm.add(algorithm)
        default_value = InventoryAlgorithmParameterValue.objects.create(
            name="default",
            parameter=parameter,
            value=1.0,
            default=True,
        )

        self.scenario.create_default_configuration()

        entry = ScenarioInventoryConfiguration.objects.get(
            scenario=self.scenario, inventory_parameter=parameter
        )
        self.assertEqual(entry.feedstock, feedstock.inventory_input)
        self.assertEqual(entry.inventory_algorithm, algorithm)
        self.assertEqual(entry.geodataset, algorithm.geodataset)
        self.assertEqual(entry.inventory_value, default_value)
        self.scenario.is_valid_configuration()
        self.scenario.catchment = Catchment.objects.create(name="Default Catchment")
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["kwargs"]["feedstock_id"], feedstock.id)
        self.assertEqual(
            plan[0]["kwargs"]["inventory_input_id"], feedstock.inventory_input.id
        )
        self.assertEqual(plan[0]["kwargs"]["feedstock_kind"], "series")
        self.assertEqual(plan[0]["kwargs"]["test_param"]["value"], 1.0)

    def test_create_default_configuration_creates_one_configuration_per_series(
        self,
    ):
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        algorithm.default = True
        algorithm.save()
        material = Material.objects.get(name="Feedstock 1")
        series_a = SampleSeries.objects.create(material=material, name="Series A")
        series_b = SampleSeries.objects.create(material=material, name="Series B")

        self.scenario.create_default_configuration()

        self.assertQuerySetEqual(
            self.scenario.feedstocks().order_by("series__name"),
            [series_a.inventory_input, series_b.inventory_input],
        )
        self.assertFalse(
            self.scenario.configuration().filter(feedstock__isnull=True).exists()
        )

    def test_create_default_configuration_with_shared_parameter_is_valid(self):
        """A parameter shared by two default algorithms is configured once per
        algorithm without tripping the duplicate-parameter validation."""
        material = Material.objects.get(name="Feedstock 1")
        SampleSeries.objects.create(material=material, name="Shared Series")
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm_a = InventoryAlgorithm.objects.get(name="Test Algorithm")
        algorithm_a.default = True
        algorithm_a.save()
        algorithm_b = InventoryAlgorithm.objects.create(
            name="Second Default Algorithm", geodataset=geodataset, default=True
        )
        algorithm_b.feedstocks.add(material)
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Yield", short_name="yield", is_required=True
        )
        parameter.inventory_algorithm.add(algorithm_a, algorithm_b)
        InventoryAlgorithmParameterValue.objects.create(
            name="default", parameter=parameter, value=2.0, default=True
        )

        self.scenario.create_default_configuration()

        self.assertEqual(
            self.scenario.configuration().filter(inventory_parameter=parameter).count(),
            2,
        )
        self.scenario.is_valid_configuration()

    def test_is_valid_configuration_rejects_duplicate_parameter_for_same_algorithm(
        self,
    ):
        material = Material.objects.get(name="Feedstock 1")
        feedstock = SampleSeries.objects.create(material=material, name="Dup Series")
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Yield", short_name="yield"
        )
        parameter.inventory_algorithm.add(algorithm)
        value = InventoryAlgorithmParameterValue.objects.create(
            name="default", parameter=parameter, value=2.0, default=True
        )
        for _ in range(2):
            ScenarioInventoryConfiguration.objects.create(
                scenario=self.scenario,
                feedstock=feedstock.inventory_input,
                geodataset=geodataset,
                inventory_algorithm=algorithm,
                inventory_parameter=parameter,
                inventory_value=value,
            )

        with self.assertRaises(ScenarioConfigurationError):
            self.scenario.is_valid_configuration()


class ScenarioResultHomogenizeTimestepsTestCase(TestCase):
    """#211: homogenize_timesteps must collect timesteps from all layers."""

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name="TS Region")
        catchment = Catchment.objects.create(name="TS Catchment", region=region)
        cls.scenario = Scenario.objects.create(
            name="TS Scenario", region=region, catchment=catchment
        )
        geodataset = GeoDataset.objects.create(name="TS Dataset", region=region)
        material = Material.objects.create(name="TS Feedstock")
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="TS Algorithm", geodataset=geodataset
        )
        cls.algorithm.feedstocks.add(material)
        cls.feedstock = SampleSeries.objects.create(
            name="TS Series", material=material
        ).inventory_input

    def tearDown(self):
        for name in list(apps.all_models["layer_manager"]):
            if name.startswith("test_ts_"):
                del apps.all_models["layer_manager"][name]

    def test_returns_empty_list_for_scenario_without_layers(self):
        result = ScenarioResult(self.scenario)
        self.assertEqual(result.timesteps, [])

    def test_collects_timesteps_from_all_layers(self):
        dist1 = TemporalDistribution.objects.create(name="TS Dist1")
        ts1 = Timestep.objects.create(name="TS T1", distribution=dist1)
        dist2 = TemporalDistribution.objects.create(name="TS Dist2")
        ts2 = Timestep.objects.create(name="TS T2", distribution=dist2)

        layer1 = Layer.objects.create(
            name="L1",
            geom_type="Point",
            table_name="test_ts_layer1",
            scenario=self.scenario,
            feedstock=self.feedstock,
            algorithm=self.algorithm,
        )
        LayerAggregatedDistribution.objects.create(
            name="AD1", distribution=dist1, layer=layer1
        )
        layer2 = Layer.objects.create(
            name="L2",
            geom_type="Point",
            table_name="test_ts_layer2",
            scenario=self.scenario,
            feedstock=self.feedstock,
            algorithm=self.algorithm,
        )
        LayerAggregatedDistribution.objects.create(
            name="AD2", distribution=dist2, layer=layer2
        )

        result = ScenarioResult(self.scenario)
        timestep_ids = {ts.id for ts in result.timesteps}
        self.assertIn(ts1.id, timestep_ids)
        self.assertIn(ts2.id, timestep_ids)

    def test_skips_aggregated_distribution_with_null_distribution(self):
        """homogenize_timesteps must not crash when distribution FK is None."""
        layer = Layer.objects.create(
            name="L_null",
            geom_type="Point",
            table_name="test_ts_layer_null",
            scenario=self.scenario,
            feedstock=self.feedstock,
            algorithm=self.algorithm,
        )
        LayerAggregatedDistribution.objects.create(
            name="AD_null", distribution=None, layer=layer
        )

        result = ScenarioResult(self.scenario)
        self.assertEqual(result.timesteps, [])


class InventoryInputTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="ii_owner")
        cls.other_user = User.objects.create(username="ii_other")
        cls.material = Material.objects.create(
            owner=cls.owner, name="II Material", publication_status="published"
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="II Sample",
            material=cls.material,
            publication_status="published",
            standalone=True,
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.owner,
            name="II Series",
            material=cls.material,
            publication_status="published",
        )

    def test_wrapper_created_for_sample_series(self):
        inventory_input = InventoryInput.objects.get(series=self.series)
        self.assertIsNone(inventory_input.sample_id)
        self.assertTrue(inventory_input.is_temporal)

    def test_wrapper_created_for_standalone_sample(self):
        inventory_input = InventoryInput.objects.get(sample=self.sample)
        self.assertIsNone(inventory_input.series_id)
        self.assertFalse(inventory_input.is_temporal)

    def test_no_wrapper_for_non_standalone_sample(self):
        sample = Sample.objects.create(
            name="II Series Member", material=self.material, series=self.series
        )
        self.assertFalse(InventoryInput.objects.filter(sample=sample).exists())

    def test_clean_requires_exactly_one_source(self):
        with self.assertRaisesMessage(
            ValidationError, "Select exactly one sample or sample series."
        ):
            InventoryInput().clean()
        with self.assertRaisesMessage(
            ValidationError, "Select exactly one sample or sample series."
        ):
            InventoryInput(sample=self.sample, series=self.series).clean()

    def test_check_constraint_enforced(self):
        sample = Sample.objects.create(
            name="II Constraint Sample", material=self.material, standalone=True
        )
        series = SampleSeries.objects.create(
            name="II Constraint Series", material=self.material
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                InventoryInput.objects.create(sample=sample, series=series)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                InventoryInput.objects.create()

    def test_clean_rejects_non_standalone_sample(self):
        sample = Sample.objects.create(
            name="II Not Standalone", material=self.material, series=self.series
        )
        inventory_input = InventoryInput(sample=sample)
        with self.assertRaises(ValidationError) as context:
            inventory_input.clean()
        self.assertIn("sample", context.exception.message_dict)

    def test_for_object_wraps_sample_series_and_input(self):
        sample_input = InventoryInput.objects.for_object(self.sample)
        self.assertEqual(sample_input.sample, self.sample)
        series_input = InventoryInput.objects.for_object(self.series)
        self.assertEqual(series_input.series, self.series)
        self.assertIs(InventoryInput.objects.for_object(series_input), series_input)

    def test_for_object_is_idempotent(self):
        first = InventoryInput.objects.for_object(self.series)
        second = InventoryInput.objects.for_object(self.series)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(InventoryInput.objects.filter(series=self.series).count(), 1)

    def test_for_object_rejects_unsupported_type(self):
        with self.assertRaises(TypeError):
            InventoryInput.objects.for_object(self.material)

    def test_for_object_rejects_non_standalone_sample(self):
        member = Sample.objects.create(
            name="II Member", material=self.material, series=self.series
        )
        with self.assertRaises(ValidationError) as context:
            InventoryInput.objects.for_object(member)
        self.assertIn("sample", context.exception.message_dict)

    def test_inventory_amount_share_requires_temporal_input(self):
        distribution = TemporalDistribution.objects.create(name="II Share Dist")
        timestep = Timestep.objects.create(
            name="II Share TS", distribution=distribution
        )
        temporal_share = InventoryAmountShare(
            feedstock=self.series.inventory_input, timestep=timestep, average=0.5
        )
        temporal_share.clean()

        static_share = InventoryAmountShare(
            feedstock=self.sample.inventory_input, timestep=timestep, average=0.5
        )
        with self.assertRaises(ValidationError) as context:
            static_share.clean()
        self.assertIn("feedstock", context.exception.message_dict)

    def test_delegated_properties(self):
        sample_input = InventoryInput.objects.get(sample=self.sample)
        series_input = InventoryInput.objects.get(series=self.series)
        self.assertEqual(sample_input.input_object, self.sample)
        self.assertEqual(series_input.input_object, self.series)
        self.assertEqual(sample_input.material, self.material)
        self.assertEqual(series_input.material, self.material)
        self.assertEqual(sample_input.name, "II Sample")
        self.assertEqual(series_input.name, "II Series")
        self.assertEqual(sample_input.kind, "sample")
        self.assertEqual(series_input.kind, "series")
        self.assertEqual(sample_input.publication_status, "published")
        self.assertEqual(str(series_input), "Series: II Material — II Series")
        self.assertEqual(str(sample_input), "Sample: II Material — II Sample")

    def test_accessible_by_user_scopes_visibility(self):
        other_private = SampleSeries.objects.create(
            owner=self.other_user,
            name="II Other Private",
            material=self.material,
            publication_status="private",
        )
        own_private = SampleSeries.objects.create(
            owner=self.owner,
            name="II Own Private",
            material=self.material,
            publication_status="private",
        )
        other_private_input = InventoryInput.objects.get(series=other_private)
        own_private_input = InventoryInput.objects.get(series=own_private)
        published_input = InventoryInput.objects.get(series=self.series)

        user_qs = InventoryInput.objects.accessible_by_user(self.owner)
        self.assertIn(own_private_input, user_qs)
        self.assertIn(published_input, user_qs)
        self.assertNotIn(other_private_input, user_qs)

        anonymous_qs = InventoryInput.objects.accessible_by_user(AnonymousUser())
        self.assertIn(published_input, anonymous_qs)
        self.assertNotIn(own_private_input, anonymous_qs)
        self.assertNotIn(other_private_input, anonymous_qs)


class FeedstockForeignKeyMetadataTestCase(TestCase):
    def referenced_tables(self, table, column):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ccu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = current_schema()
                  AND tc.table_name = %s
                  AND kcu.column_name = %s
                """,
                [table, column],
            )
            return {row[0] for row in cursor.fetchall()}

    def test_inventory_amount_share_feedstock_fk_targets_inventory_input(self):
        self.assertEqual(
            {"inventories_inventoryinput"},
            self.referenced_tables("inventories_inventoryamountshare", "feedstock_id"),
        )

    def test_scenario_configuration_feedstock_fk_targets_inventory_input(self):
        self.assertEqual(
            {"inventories_inventoryinput"},
            self.referenced_tables(
                "inventories_scenarioinventoryconfiguration", "feedstock_id"
            ),
        )


class InventoryInputBackfillTestCase(TestCase):
    def test_backfill_preserves_series_ids_offsets_samples_and_resets_sequence(
        self,
    ):
        migration = importlib.import_module(
            "inventories.migrations.0008_inventoryinput_and_more"
        )
        material = Material.objects.create(name="Backfill Material")
        sample = Sample.objects.create(
            name="Backfill Sample", material=material, standalone=True
        )
        series = SampleSeries.objects.create(name="Backfill Series", material=material)
        member = Sample.objects.create(
            name="Backfill Member", material=material, series=series
        )
        InventoryInput.objects.all().delete()

        migration.create_inventory_inputs(apps, SimpleNamespace(connection=connection))

        series_input = InventoryInput.objects.get(series=series)
        self.assertEqual(series_input.pk, series.pk)
        offset = SampleSeries.objects.order_by("-pk").first().pk
        sample_input = InventoryInput.objects.get(sample=sample)
        self.assertEqual(sample_input.pk, offset + sample.pk)
        self.assertFalse(InventoryInput.objects.filter(sample=member).exists())

        region = Region.objects.create(name="Backfill Region")
        scenario = Scenario.objects.create(name="Backfill Scenario", region=region)
        geodataset = GeoDataset.objects.create(name="Backfill Dataset", region=region)
        algorithm = InventoryAlgorithm.objects.create(
            name="Backfill Algorithm", geodataset=geodataset
        )
        config = ScenarioInventoryConfiguration.objects.create(
            scenario=scenario,
            feedstock_id=series.pk,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
        )
        self.assertEqual(config.feedstock, series_input)

        distribution = TemporalDistribution.objects.create(name="Backfill Dist")
        timestep = Timestep.objects.create(
            name="Backfill TS", distribution=distribution
        )
        share = InventoryAmountShare.objects.create(
            scenario=scenario,
            feedstock_id=series.pk,
            timestep=timestep,
            average=0.5,
        )
        self.assertEqual(share.feedstock, series_input)

        layer = Layer.objects.create(
            name="Backfill Layer",
            geom_type="Point",
            table_name="backfill_layer",
            scenario=scenario,
            feedstock_id=series.pk,
            algorithm=algorithm,
        )
        self.assertEqual(layer.feedstock, series_input)
        layer.delete()

        later_series = SampleSeries.objects.create(
            name="Backfill Later Series", material=material
        )
        later_input = InventoryInput.objects.get(series=later_series)
        self.assertNotIn(later_input.pk, [series_input.pk, sample_input.pk])


class InventoryInputReverseMigrationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.material = Material.objects.create(name="Reverse Material")
        cls.region = Region.objects.create(name="Reverse Region")
        cls.scenario = Scenario.objects.create(
            name="Reverse Scenario", region=cls.region
        )
        cls.geodataset = GeoDataset.objects.create(
            name="Reverse Dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Reverse Algorithm", geodataset=cls.geodataset
        )

    @staticmethod
    def reverse_feedstock_fks():
        migration = importlib.import_module(
            "inventories.migrations.0008_inventoryinput_and_more"
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with connection.schema_editor() as schema_editor:
            migration.retarget_feedstock_fks_to_sampleseries(None, schema_editor)

    def test_reverse_maps_temporal_rows_through_series_id(self):
        series = SampleSeries.objects.create(
            name="Reverse Series", material=self.material
        )
        wrapper = series.inventory_input
        wrapper.delete()
        wrapper = InventoryInput.objects.create(pk=series.pk + 100000, series=series)
        config = ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=wrapper,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
        )

        self.reverse_feedstock_fks()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT feedstock_id FROM inventories_scenarioinventoryconfiguration WHERE id = %s",
                [config.pk],
            )
            self.assertEqual(cursor.fetchone()[0], series.pk)

    def test_reverse_refuses_standalone_rows(self):
        sample = Sample.objects.create(
            name="Reverse Sample", material=self.material, standalone=True
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=sample.inventory_input,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
        )

        with self.assertRaises(IrreversibleError):
            self.reverse_feedstock_fks()


class ScenarioInventoryInputTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="scenario_input_owner")
        cls.other_user = User.objects.create(username="scenario_input_other")
        cls.region = Region.objects.create(name="SI Region")
        cls.catchment = Catchment.objects.create(name="SI Catchment", region=cls.region)
        cls.scenario = Scenario.objects.create(
            name="SI Scenario", region=cls.region, catchment=cls.catchment
        )
        cls.material = Material.objects.create(
            owner=cls.owner, name="SI Material", publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.owner,
            name="SI Series",
            material=cls.material,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="SI Sample",
            material=cls.material,
            publication_status="published",
            standalone=True,
        )
        cls.geodataset = GeoDataset.objects.create(name="SI Dataset", region=cls.region)
        cls.series_algorithm = InventoryAlgorithm.objects.create(
            name="SI Series Algorithm", geodataset=cls.geodataset
        )
        cls.series_algorithm.feedstocks.add(cls.material)
        cls.static_algorithm = InventoryAlgorithm.objects.create(
            name="SI Static Algorithm",
            geodataset=cls.geodataset,
            supports_standalone_samples=True,
        )
        cls.static_algorithm.feedstocks.add(cls.material)

    def test_algorithm_capability_defaults(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="SI Defaults", geodataset=self.geodataset
        )
        self.assertTrue(algorithm.supports_sample_series)
        self.assertFalse(algorithm.supports_standalone_samples)

    def test_available_feedstocks_returns_both_kinds(self):
        available = self.scenario.available_feedstocks()
        self.assertIn(self.series.inventory_input, available)
        self.assertIn(self.sample.inventory_input, available)

    def test_available_feedstocks_excludes_unsupported_materials(self):
        other_material = Material.objects.create(name="SI Other Material")
        other_sample = Sample.objects.create(
            name="SI Other Sample", material=other_material, standalone=True
        )
        available = self.scenario.available_feedstocks()
        self.assertNotIn(other_sample.inventory_input, available)

    def test_available_feedstocks_scoped_to_user(self):
        private_sample = Sample.objects.create(
            owner=self.other_user,
            name="SI Other Private Sample",
            material=self.material,
            standalone=True,
        )
        available = self.scenario.available_feedstocks(user=self.owner)
        self.assertNotIn(private_sample.inventory_input, available)
        available = self.scenario.available_feedstocks(user=self.other_user)
        self.assertIn(private_sample.inventory_input, available)

    def test_available_feedstocks_excludes_series_member_sample_wrappers(self):
        member = Sample.objects.create(
            name="SI Member",
            material=self.material,
            series=self.series,
            publication_status="published",
        )
        member_input = InventoryInput.objects.create(sample=member)
        self.assertNotIn(member_input, self.scenario.available_feedstocks())
        self.assertNotIn(
            member_input, self.scenario.available_feedstocks(user=self.owner)
        )

    def test_available_geodatasets_uses_underlying_material(self):
        wrapper = self.sample.inventory_input
        wrapper.delete()
        wrapper = InventoryInput.objects.create(
            pk=self.material.pk + 999999, sample=self.sample
        )
        self.assertNotEqual(wrapper.pk, self.material.pk)
        available = self.scenario.available_geodatasets(feedstock=wrapper)
        self.assertIn(self.geodataset, available)

    def test_available_geodatasets_filters_by_input_kind(self):
        series_only_dataset = GeoDataset.objects.create(
            name="SI Series Only Dataset", region=self.region
        )
        series_only_algorithm = InventoryAlgorithm.objects.create(
            name="SI Series Only", geodataset=series_only_dataset
        )
        series_only_algorithm.feedstocks.add(self.material)

        self.assertIn(
            series_only_dataset,
            self.scenario.available_geodatasets(feedstock=self.series.inventory_input),
        )
        self.assertNotIn(
            series_only_dataset,
            self.scenario.available_geodatasets(feedstock=self.sample.inventory_input),
        )
        self.assertNotIn(
            series_only_dataset,
            self.scenario.remaining_geodataset_options(
                feedstock=self.sample.inventory_input
            ),
        )

    def test_evaluated_and_remaining_geodatasets_use_underlying_material(self):
        wrapper = self.sample.inventory_input
        wrapper.delete()
        wrapper = InventoryInput.objects.create(
            pk=self.material.pk + 999999, sample=self.sample
        )
        other_dataset = GeoDataset.objects.create(
            name="SI Other Dataset", region=self.region
        )
        other_algorithm = InventoryAlgorithm.objects.create(
            name="SI Other Algorithm", geodataset=other_dataset
        )
        other_algorithm.feedstocks.add(self.material)

        self.scenario.add_inventory_algorithm(wrapper, self.static_algorithm)

        self.assertIn(
            self.geodataset,
            self.scenario.evaluated_geodatasets(feedstock=wrapper),
        )
        remaining = self.scenario.remaining_geodataset_options(
            feedstock=self.series.inventory_input
        )
        self.assertNotIn(self.geodataset, remaining)
        self.assertIn(other_dataset, remaining)

    def test_feedstocks_returns_inventory_inputs(self):
        self.scenario.add_inventory_algorithm(self.series, self.series_algorithm)
        feedstocks = self.scenario.feedstocks()
        self.assertQuerySetEqual(feedstocks, [self.series.inventory_input])

    def test_add_inventory_algorithm_accepts_all_wrapper_types(self):
        self.scenario.add_inventory_algorithm(self.series, self.series_algorithm)
        self.scenario.add_inventory_algorithm(self.sample, self.static_algorithm)
        self.scenario.add_inventory_algorithm(
            self.sample.inventory_input, self.static_algorithm
        )
        self.assertTrue(
            self.scenario.configuration()
            .filter(feedstock=self.series.inventory_input)
            .exists()
        )
        self.assertTrue(
            self.scenario.configuration()
            .filter(feedstock=self.sample.inventory_input)
            .exists()
        )

    def test_add_inventory_algorithm_rejects_unsupported_kind(self):
        with self.assertRaises(FeedstockNotImplemented):
            self.scenario.add_inventory_algorithm(self.sample, self.series_algorithm)

    def test_default_configuration_uses_series_inputs_only(self):
        self.static_algorithm.default = True
        self.static_algorithm.save()
        self.series_algorithm.default = True
        self.series_algorithm.save()

        self.scenario.create_default_configuration()

        self.assertTrue(
            self.scenario.configuration()
            .filter(feedstock=self.series.inventory_input)
            .exists()
        )
        self.assertFalse(
            self.scenario.configuration()
            .filter(feedstock=self.sample.inventory_input)
            .exists()
        )

    def test_default_configuration_skips_series_for_static_only_algorithm(self):
        self.static_algorithm.default = True
        self.static_algorithm.supports_sample_series = False
        self.static_algorithm.save()
        self.series_algorithm.default = True
        self.series_algorithm.save()

        self.scenario.create_default_configuration()

        configuration = self.scenario.configuration()
        self.assertTrue(
            configuration.filter(
                feedstock=self.series.inventory_input,
                inventory_algorithm=self.series_algorithm,
            ).exists()
        )
        self.assertFalse(
            configuration.filter(inventory_algorithm=self.static_algorithm).exists()
        )

    def test_sample_losing_standalone_retires_inventory_input(self):
        sample = Sample.objects.create(
            owner=self.owner,
            name="SI Transient Sample",
            material=self.material,
            publication_status="published",
            standalone=True,
        )
        wrapper = sample.inventory_input
        self.scenario.add_inventory_algorithm(sample, self.static_algorithm)
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        sample.standalone = False
        sample.series = self.series
        sample.save()

        self.assertFalse(InventoryInput.objects.filter(pk=wrapper.pk).exists())
        self.assertFalse(
            self.scenario.configuration().filter(feedstock_id=wrapper.pk).exists()
        )
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)

    def test_execution_plan_includes_feedstock_kind(self):
        self.scenario.add_inventory_algorithm(self.series, self.series_algorithm)
        self.scenario.add_inventory_algorithm(self.sample, self.static_algorithm)

        plan = {
            entry["kwargs"]["inventory_input_id"]: entry["kwargs"]
            for entry in self.scenario.inventory_execution_plan()
        }

        series_kwargs = plan[self.series.inventory_input.pk]
        self.assertEqual(series_kwargs["feedstock_id"], self.series.pk)
        self.assertEqual(series_kwargs["feedstock_kind"], "series")
        sample_kwargs = plan[self.sample.inventory_input.pk]
        self.assertEqual(sample_kwargs["feedstock_id"], self.sample.pk)
        self.assertEqual(sample_kwargs["feedstock_kind"], "sample")

    def test_execution_plan_separates_adapter_and_domain_ids(self):
        wrapper = self.series.inventory_input
        wrapper.delete()
        wrapper = InventoryInput.objects.create(
            pk=self.series.pk + 999999, series=self.series
        )
        self.assertNotEqual(wrapper.pk, self.series.pk)

        self.scenario.add_inventory_algorithm(wrapper, self.series_algorithm)
        plan = self.scenario.inventory_execution_plan()

        kwargs = plan[0]["kwargs"]
        self.assertEqual(kwargs["feedstock_id"], self.series.pk)
        self.assertEqual(kwargs["inventory_input_id"], wrapper.pk)
        # A legacy algorithm resolving the domain object by feedstock_id
        # still finds the series.
        self.assertEqual(
            SampleSeries.objects.get(id=kwargs["feedstock_id"]), self.series
        )

    def test_available_inventory_algorithms_filters_supported_kind(self):
        algorithms = self.scenario.available_inventory_algorithms(
            feedstock=self.sample.inventory_input
        )
        self.assertIn(self.static_algorithm, algorithms)
        self.assertNotIn(self.series_algorithm, algorithms)

        algorithms = self.scenario.available_inventory_algorithms(
            feedstock=self.series.inventory_input
        )
        self.assertIn(self.series_algorithm, algorithms)
        self.assertIn(self.static_algorithm, algorithms)
