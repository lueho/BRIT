from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from distributions.models import TemporalDistribution, Timestep
from layer_manager.models import Layer, LayerAggregatedDistribution
from maps.models import Catchment, Region
from materials.models import SampleSeries
from sources.greenhouses.inventory.algorithms import (
    InventoryAlgorithms as GreenhouseInventoryAlgorithms,
)

from ..evaluations import ScenarioResult
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

    def test_scenario_catchment_change_clears_failure_metadata(self):
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        self.set_failed_status(algorithm)

        self.scenario.catchment = Catchment.objects.create(
            name="Other Catchment", region=self.scenario.region
        )
        self.scenario.save()

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(self.scenario.scenariostatus.failed_algorithm)
        self.assertEqual(self.scenario.scenariostatus.failure_message, "")

    def test_scenario_region_change_marks_changed(self):
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        self.scenario.region = Region.objects.create(name="Other Region")
        self.scenario.save()

        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)

    def test_scenario_catchment_id_update_field_marks_changed(self):
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        self.scenario.catchment_id = Catchment.objects.create(
            name="Other Catchment", region=self.scenario.region
        ).pk
        self.scenario.save(update_fields=["catchment_id"])

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.CHANGED)

    def test_unsaved_region_edit_outside_update_fields_keeps_finished_status(self):
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        self.scenario.region = Region.objects.create(name="Unsaved Region")
        self.scenario.save(update_fields=["catchment_id"])

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)

    def test_scenario_metadata_edit_keeps_finished_status(self):
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        self.scenario.name = "Renamed Scenario"
        self.scenario.description = "New description"
        self.scenario.save()

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)

    def test_publishing_scenario_keeps_finished_status(self):
        self.scenario.set_status(ScenarioStatus.Status.FINISHED)

        self.scenario.publication_status = Scenario.STATUS_PUBLISHED
        self.scenario.save(update_fields=["publication_status"])

        self.scenario.scenariostatus.refresh_from_db()
        self.assertEqual(self.scenario.status, ScenarioStatus.Status.FINISHED)

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
                "inventories.algorithms",
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
        execute.assert_called_once_with(
            example="value", geodataset_id=algorithm.geodataset_id
        )

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
        self.assertIsNot(
            config[7][algorithm.task_reference], execution_plan[0]["kwargs"]
        )

    def test_is_valid_configuration_scopes_required_parameters_to_current_scenario(
        self,
    ):
        feedstock = Material.objects.get(name="Feedstock 1")
        material = feedstock
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

    def test_inventory_algorithm_config_is_scoped_to_feedstock_and_uses_short_names(
        self,
    ):
        material = Material.objects.get(name="Feedstock 1")
        other_material = Material.objects.get(name="Feedstock 2")
        feedstock = material
        other_feedstock = other_material
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
            feedstock=feedstock,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=value,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=other_feedstock,
            geodataset=geodataset,
            inventory_algorithm=algorithm,
            inventory_parameter=parameter,
            inventory_value=other_value,
        )

        config = self.scenario.inventory_algorithm_config(algorithm, feedstock)

        self.assertEqual(config["scenario"], self.scenario)
        self.assertEqual(config["feedstock"], feedstock)
        self.assertEqual(config["geodataset"], geodataset)
        self.assertEqual(config["inventory_algorithm"], algorithm)
        self.assertEqual(config["parameters"], [{"point_yield": value.id}])

    def test_add_inventory_algorithm_creates_config_rows_atomically(self):
        """add_inventory_algorithm must create all config rows inside transaction.atomic."""
        material = Material.objects.get(name="Feedstock 1")
        feedstock = material
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
            scenario=self.scenario, inventory_algorithm=algorithm, feedstock=feedstock
        )
        self.assertTrue(configs.exists())

    def test_scenario_status_updates_when_referenced_parameter_value_changes(self):
        """#212: Changing a referenced InventoryAlgorithmParameterValue must
        mark all scenarios that use it as CHANGED."""
        material = Material.objects.get(name="Feedstock 1")
        feedstock = material
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
            feedstock=feedstock,
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
        feedstock = material
        geodataset = GeoDataset.objects.get(name="Test Dataset")
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock,
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
        parameter and feedstock material even though
        InventoryAlgorithmParameter.inventory_algorithm is a ManyToManyField."""
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        algorithm.default = True
        algorithm.save()
        feedstock = Material.objects.get(name="Feedstock 1")

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
        self.assertEqual(entry.feedstock, feedstock)
        self.assertEqual(entry.inventory_algorithm, algorithm)
        self.assertEqual(entry.geodataset, algorithm.geodataset)
        self.assertEqual(entry.inventory_value, default_value)
        self.scenario.is_valid_configuration()
        self.scenario.catchment = Catchment.objects.create(name="Default Catchment")
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["kwargs"]["feedstock_id"], feedstock.id)
        self.assertEqual(plan[0]["kwargs"]["test_param"]["value"], 1.0)

    def test_create_default_configuration_creates_one_configuration_per_material(
        self,
    ):
        algorithm = InventoryAlgorithm.objects.get(name="Test Algorithm")
        algorithm.default = True
        algorithm.save()
        material = Material.objects.get(name="Feedstock 1")
        other_material = Material.objects.get(name="Feedstock 2")
        algorithm.feedstocks.add(other_material)
        SampleSeries.objects.create(material=material, name="Series A")
        SampleSeries.objects.create(material=material, name="Series B")

        self.scenario.create_default_configuration()

        # Multiple series of a material collapse into a single material-level
        # configuration — the series is an optional temporal profile.
        self.assertQuerySetEqual(
            self.scenario.feedstocks().order_by("name"),
            [material, other_material],
        )
        self.assertFalse(
            self.scenario.configuration().filter(feedstock__isnull=True).exists()
        )

    def test_create_default_configuration_with_shared_parameter_is_valid(self):
        """A parameter shared by two default algorithms is configured once per
        algorithm without tripping the duplicate-parameter validation."""
        material = Material.objects.get(name="Feedstock 1")
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
        feedstock = material
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
                feedstock=feedstock,
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
        cls.feedstock = material

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


class MaterialFeedstockContractTestCase(TestCase):
    """Feedstock selection is material-based.

    ``ScenarioInventoryConfiguration.feedstock`` identifies a Material; a
    SampleSeries is an optional temporal profile for algorithms that need
    seasonal data, not the carrier of the material identity.
    """

    @classmethod
    def setUpTestData(cls):
        cls.material = Material.objects.create(name="Contract Material")
        cls.other_material = Material.objects.create(name="Other Material")
        cls.region = Region.objects.create(name="Contract Region")
        cls.catchment = Catchment.objects.create(
            name="Contract Catchment", region=cls.region
        )
        cls.scenario = Scenario.objects.create(
            name="Contract Scenario", region=cls.region, catchment=cls.catchment
        )
        cls.geodataset = GeoDataset.objects.create(
            name="Contract Dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Contract Algorithm", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(cls.material)

    def test_available_feedstocks_returns_materials(self):
        feedstocks = self.scenario.available_feedstocks()
        self.assertQuerySetEqual(feedstocks, [self.material])
        for feedstock in feedstocks:
            self.assertIsInstance(feedstock, Material)

    def test_configuration_accepts_material_as_feedstock(self):
        entry = ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.material,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
        )
        self.assertIsInstance(entry.feedstock, Material)
        self.assertEqual(entry.feedstock, self.material)

    def test_scenario_feedstocks_returns_materials(self):
        self.scenario.add_inventory_algorithm(self.material, self.algorithm)
        self.assertQuerySetEqual(self.scenario.feedstocks(), [self.material])

    def test_add_inventory_algorithm_stores_optional_sample_series(self):
        series = SampleSeries.objects.create(
            material=self.material, name="Contract Series"
        )
        self.scenario.add_inventory_algorithm(
            self.material, self.algorithm, sample_series=series
        )
        entry = self.scenario.configuration().first()
        self.assertEqual(entry.feedstock, self.material)
        self.assertEqual(entry.sample_series, series)

    def test_execution_plan_emits_material_id_and_series_id(self):
        series = SampleSeries.objects.create(
            material=self.material, name="Contract Series"
        )
        self.scenario.add_inventory_algorithm(
            self.material, self.algorithm, sample_series=series
        )
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["kwargs"]["feedstock_id"], self.material.pk)
        self.assertEqual(plan[0]["kwargs"]["sample_series_id"], series.pk)

    def test_execution_plan_omits_series_id_when_unset(self):
        self.scenario.add_inventory_algorithm(self.material, self.algorithm)
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(plan[0]["kwargs"]["feedstock_id"], self.material.pk)
        self.assertNotIn("sample_series_id", plan[0]["kwargs"])


def _square(x0, y0, size):
    from django.contrib.gis.geos import MultiPolygon, Polygon

    x1, y1 = x0 + size, y0 + size
    return MultiPolygon(
        Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=4326
    )


def _region_with_borders(name, geom):
    from maps.models import GeoPolygon

    return Region.objects.create(
        name=name, borders=GeoPolygon.objects.create(geom=geom)
    )


class ScenarioEnclosingRegionGeodatasetTestCase(TestCase):
    """A dataset attached to a region that spatially encloses the scenario
    region (e.g. a country-wide dataset for a municipality scenario) is
    offered to the scenario like a dataset of the scenario region itself."""

    @classmethod
    def setUpTestData(cls):
        cls.feedstock = Material.objects.create(name="Enclosing feedstock")
        country = _region_with_borders("Country", _square(0, 0, 10))
        municipality = _region_with_borders("Municipality", _square(2, 2, 2))
        elsewhere = _region_with_borders("Elsewhere", _square(20, 20, 2))
        cls.scenario = Scenario.objects.create(
            name="Municipality scenario", region=municipality
        )
        cls.country_dataset = GeoDataset.objects.create(
            name="Country dataset", region=country
        )
        cls.elsewhere_dataset = GeoDataset.objects.create(
            name="Elsewhere dataset", region=elsewhere
        )
        cls.country_algorithm = InventoryAlgorithm.objects.create(
            name="Country algorithm", geodataset=cls.country_dataset, default=True
        )
        cls.country_algorithm.feedstocks.add(cls.feedstock)
        elsewhere_algorithm = InventoryAlgorithm.objects.create(
            name="Elsewhere algorithm", geodataset=cls.elsewhere_dataset, default=True
        )
        elsewhere_algorithm.feedstocks.add(cls.feedstock)

    def test_compatible_geodatasets_include_enclosing_region(self):
        datasets = self.scenario.compatible_geodatasets()
        self.assertIn(self.country_dataset, datasets)
        self.assertNotIn(self.elsewhere_dataset, datasets)

    def test_partially_overlapping_region_is_not_compatible(self):
        partial = _region_with_borders("Partial", _square(2.5, 2.5, 3))
        partial_dataset = GeoDataset.objects.create(
            name="Partial dataset", region=partial
        )
        self.assertNotIn(partial_dataset, self.scenario.compatible_geodatasets())

    def test_region_with_minor_border_mismatch_is_compatible(self):
        shifted = _region_with_borders("Shifted", _square(2.01, 2, 2))
        shifted_dataset = GeoDataset.objects.create(
            name="Shifted dataset", region=shifted
        )
        self.assertIn(shifted_dataset, self.scenario.compatible_geodatasets())

    def test_scenario_without_region_borders_matches_exact_region_only(self):
        region = Region.objects.create(name="No borders")
        own_dataset = GeoDataset.objects.create(name="Own dataset", region=region)
        scenario = Scenario.objects.create(name="Borderless", region=region)
        self.assertQuerySetEqual(scenario.compatible_geodatasets(), [own_dataset])

    def test_available_geodatasets_include_enclosing_region(self):
        self.assertQuerySetEqual(
            self.scenario.available_geodatasets(feedstock=self.feedstock),
            [self.country_dataset],
        )

    def test_available_inventory_algorithms_include_enclosing_region(self):
        self.assertQuerySetEqual(
            self.scenario.available_inventory_algorithms(feedstock=self.feedstock),
            [self.country_algorithm],
        )
        self.assertIn(self.feedstock, self.scenario.available_feedstocks())

    def test_default_configuration_uses_enclosing_region_defaults(self):
        self.assertQuerySetEqual(
            self.scenario.default_inventory_algorithms(), [self.country_algorithm]
        )
