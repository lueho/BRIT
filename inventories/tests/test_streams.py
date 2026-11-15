"""Tests for inventory streams: stored definition, invalidation and evaluation."""

from uuid import uuid4

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from inventories.evaluator import BaseKind, Condition, Term
from inventories.exceptions import BlockedRunningScenario
from inventories.models import (
    InventoryStream,
    Scenario,
    ScenarioConfigurationError,
    ScenarioStatus,
    StreamFactor,
    StreamFilter,
)
from inventories.tasks import finalize_inventory, run_inventory_stream
from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material
from sources.greenhouses.models import NantesGreenhouses


def aggregated_value(layer, name):
    return layer.layeraggregatedvalue_set.get(name=name)


class StreamTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Stream Region", country="DE")
        cls.region.geom = MultiPolygon(
            Polygon(((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)), srid=4326)
        )
        cls.region.save()
        cls.catchment = Catchment.objects.create(name="Stream", region=cls.region)
        cls.material = Material.objects.create(name="Stream Material")
        cls.scenario = Scenario.objects.create(
            name="Stream Scenario", region=cls.region, catchment=cls.catchment
        )
        cls.dataset = GeoDataset.objects.create(
            name="Greenhouses", region=cls.region, model_name="NantesGreenhouses"
        )
        for x, culture in ((0.5, "Tomato"), (-0.5, "Cucumber"), (5, "Tomato")):
            NantesGreenhouses.objects.create(
                geom=Point(x, 0.5, srid=4326), culture_1=culture
            )

    def direct_stream(self, **kwargs):
        kwargs.setdefault("base_value", 100.0)
        kwargs.setdefault("base_unit", "Mg / year")
        return InventoryStream.objects.create(
            scenario=self.scenario,
            material=self.material,
            base_kind=BaseKind.DIRECT,
            **kwargs,
        )

    def count_stream(self):
        return InventoryStream.objects.create(
            scenario=self.scenario,
            material=self.material,
            base_kind=BaseKind.FEATURE_COUNT,
            geodataset=self.dataset,
        )

    def set_status(self, status, run_id=None):
        scenario_status = self.scenario.scenariostatus
        scenario_status.status = status
        scenario_status.run_id = run_id
        scenario_status.save(update_fields=["status", "run_id"])

    def status(self):
        return ScenarioStatus.objects.get(scenario=self.scenario).status


class StreamDefinitionTestCase(StreamTestBase):
    def test_spec_lists_factors_in_order_and_all_filters(self):
        stream = self.count_stream()
        StreamFactor.objects.create(stream=stream, symbol="share", value=0.5, order=2)
        StreamFactor.objects.create(
            stream=stream,
            symbol="unit_yield",
            value=25.0,
            standard_deviation=2.5,
            unit="kg / year",
            order=1,
        )
        StreamFilter.objects.create(
            stream=stream, column="culture_1", operator="eq", value="Tomato"
        )

        spec = stream.spec()

        self.assertEqual(spec.base_kind, BaseKind.FEATURE_COUNT)
        self.assertEqual(spec.geodataset, self.dataset)
        self.assertEqual(
            spec.factors,
            (Term("unit_yield", 25.0, 2.5, "kg / year"), Term("share", 0.5, None, "")),
        )
        self.assertEqual(spec.filters, (Condition("culture_1", "eq", "Tomato"),))

    def test_direct_stream_carries_its_amount_as_base_term(self):
        stream = self.direct_stream(base_standard_deviation=10.0)
        self.assertEqual(stream.spec().base, Term("amount", 100.0, 10.0, "Mg / year"))

    def test_dataset_base_requires_a_geodataset(self):
        stream = InventoryStream(
            scenario=self.scenario,
            material=self.material,
            base_kind=BaseKind.FEATURE_COUNT,
        )
        with self.assertRaises(ValidationError):
            stream.full_clean()

    def test_direct_base_requires_an_amount(self):
        stream = InventoryStream(
            scenario=self.scenario, material=self.material, base_kind=BaseKind.DIRECT
        )
        with self.assertRaises(ValidationError):
            stream.full_clean()

    def test_factor_symbol_must_be_an_identifier(self):
        factor = StreamFactor(stream=self.direct_stream(), symbol="dry matter", value=1)
        with self.assertRaises(ValidationError):
            factor.full_clean()

    def test_label_falls_back_to_the_base_quantity(self):
        self.assertEqual(self.count_stream().label, "Number of features")
        self.assertEqual(self.direct_stream(name="Reported").label, "Reported")

    def test_streams_alone_make_a_valid_configuration(self):
        with self.assertRaises(ScenarioConfigurationError):
            self.scenario.is_valid_configuration()
        self.direct_stream()
        self.scenario.is_valid_configuration()


class StreamInvalidationTestCase(StreamTestBase):
    def test_changes_invalidate_a_finished_evaluation(self):
        stream = self.direct_stream()
        changes = (
            lambda: StreamFactor.objects.create(stream=stream, symbol="a", value=1),
            lambda: StreamFilter.objects.create(
                stream=stream, column="culture_1", operator="eq", value="Tomato"
            ),
            lambda: stream.factors.first().delete(),
            lambda: stream.filters.first().delete(),
            lambda: stream.save(),
            lambda: stream.delete(),
        )
        for change in changes:
            self.set_status(ScenarioStatus.Status.FINISHED)
            change()
            self.assertEqual(self.status(), ScenarioStatus.Status.CHANGED)

    def test_changes_are_blocked_while_the_scenario_is_evaluated(self):
        stream = self.direct_stream()
        factor = StreamFactor.objects.create(stream=stream, symbol="a", value=1)
        self.set_status(ScenarioStatus.Status.RUNNING, uuid4())
        blocked = (
            lambda: self.direct_stream(),
            lambda: stream.save(),
            lambda: StreamFactor.objects.create(stream=stream, symbol="b", value=1),
            lambda: factor.delete(),
            lambda: stream.delete(),
        )
        for change in blocked:
            # The savepoint keeps the refused write from poisoning the test
            # transaction.
            with self.assertRaises(BlockedRunningScenario), transaction.atomic():
                change()


class StreamEvaluationTestCase(StreamTestBase):
    def run_stream(self, stream):
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        self.assertTrue(
            run_inventory_stream.run(
                stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        )
        finalize_inventory.run(
            [True], self.scenario.id, str(run_id), [["stream", stream.id]]
        )
        return Layer.objects.get(scenario=self.scenario, stream=stream)

    def test_stream_evaluates_inside_the_scenario_catchment(self):
        stream = self.count_stream()
        StreamFactor.objects.create(
            stream=stream, symbol="unit_yield", value=25.0, unit="kg / year"
        )
        result = stream.evaluate()
        values = {v["name"]: v["value"] for v in result["aggregated_values"]}
        self.assertEqual(values["Count"], 2)
        self.assertAlmostEqual(values["Total production"], 0.05)

    def test_run_publishes_a_result_layer_for_the_stream(self):
        stream = self.count_stream()
        StreamFactor.objects.create(
            stream=stream, symbol="unit_yield", value=25.0, unit="kg / year"
        )

        layer = self.run_stream(stream)

        self.assertEqual(self.status(), ScenarioStatus.Status.FINISHED)
        self.assertFalse(layer.staged)
        self.assertEqual(layer.feedstock, self.material)
        self.assertIsNone(layer.algorithm)
        self.assertEqual(layer.get_feature_collection().objects.count(), 2)
        self.assertAlmostEqual(aggregated_value(layer, "Total production").value, 0.05)

    def test_two_streams_of_one_material_keep_separate_layers(self):
        first = self.run_stream(self.direct_stream(name="Reported"))
        second = self.direct_stream(name="Estimated", base_value=40.0)
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        for stream_id in (first.stream_id, second.id):
            run_inventory_stream.run(
                stream_id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        finalize_inventory.run(
            [True, True],
            self.scenario.id,
            str(run_id),
            [["stream", first.stream_id], ["stream", second.id]],
        )
        layers = Layer.objects.filter(scenario=self.scenario)
        self.assertEqual(layers.count(), 2)
        self.assertEqual(
            sorted(aggregated_value(layer, "Total production").value for layer in layers),
            [40.0, 100.0],
        )

    def test_layer_of_a_removed_stream_is_dropped_on_the_next_run(self):
        removed = self.run_stream(self.direct_stream(name="Removed")).stream
        kept = self.direct_stream(name="Kept")
        removed_layer_id = Layer.objects.get(stream=removed).id
        self.set_status(ScenarioStatus.Status.CHANGED)
        removed.delete()
        self.run_stream(kept)
        self.assertFalse(Layer.all_objects.filter(id=removed_layer_id).exists())
        self.assertEqual(Layer.objects.filter(scenario=self.scenario).count(), 1)

    def test_failing_stream_marks_the_scenario_failed(self):
        stream = self.count_stream()
        StreamFilter.objects.create(
            stream=stream, column="no_such_column", operator="eq", value="x"
        )
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        with self.assertRaises(Exception):
            run_inventory_stream.run(
                stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        scenario_status = ScenarioStatus.objects.get(scenario=self.scenario)
        self.assertEqual(scenario_status.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario_status.failed_stream, stream)
        self.assertIn("no_such_column", scenario_status.failure_message)

    def test_run_inventory_plans_streams(self):
        stream = self.direct_stream()
        plan = self.scenario.stream_execution_plan()
        self.assertEqual([entry.id for entry in plan], [stream.id])
