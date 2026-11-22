"""Tests for inventory streams: stored definition, invalidation and evaluation."""

from uuid import uuid4

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from brit.templatetags.custom_tags import amount
from inventories.evaluations import ScenarioResult
from inventories.evaluator import BaseKind, Condition, Term
from inventories.exceptions import BlockedRunningScenario
from inventories.models import (
    InventoryStream,
    RunningTask,
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
from utils.object_management.models import User


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

    def yielding_count_stream(self):
        """A count stream whose chain gives a mass per year."""
        stream = self.count_stream()
        StreamFactor.objects.create(
            stream=stream, symbol="unit_yield", value=1.0, unit="Mg / year"
        )
        return stream

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
            sorted(
                aggregated_value(layer, "Total production").value for layer in layers
            ),
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

    def test_production_per_feedstock_adds_streams_of_one_material(self):
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
        production = ScenarioResult(self.scenario).total_production_per_feedstock()
        self.assertEqual(production.data, {"Stream Material": 140.0})
        self.assertEqual(production.unit, "Mg/a")

    def test_column_sum_with_a_long_base_unit_is_stored(self):
        NantesGreenhouses.objects.filter(culture_1="Cucumber").update(surface_ha=2.0)
        stream = InventoryStream.objects.create(
            scenario=self.scenario,
            material=self.material,
            base_kind=BaseKind.COLUMN_SUM,
            geodataset=self.dataset,
            base_column="surface_ha",
            base_unit="kilograms / year",
        )
        layer = self.run_stream(stream)
        total = aggregated_value(layer, "Sum")
        self.assertEqual(total.unit, "kilograms / year")
        self.assertAlmostEqual(total.value, 2.0)
        self.assertAlmostEqual(aggregated_value(layer, "Total production").value, 0.002)

    def test_failing_stream_marks_the_scenario_failed(self):
        stream = self.yielding_count_stream()
        StreamFilter.objects.create(
            stream=stream, column="no_such_column", operator="eq", value="x"
        )
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        with self.assertRaises(ImproperlyConfigured):
            run_inventory_stream.run(
                stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        scenario_status = ScenarioStatus.objects.get(scenario=self.scenario)
        self.assertEqual(scenario_status.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario_status.failed_stream, stream)
        self.assertIn("no_such_column", scenario_status.failure_message)

    def test_stream_that_yields_no_amount_of_material_fails(self):
        stream = self.count_stream()
        StreamFactor.objects.create(
            stream=stream, symbol="length", value=1.0, unit="meter"
        )
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        with self.assertRaises(ImproperlyConfigured):
            run_inventory_stream.run(
                stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        scenario_status = ScenarioStatus.objects.get(scenario=self.scenario)
        self.assertEqual(scenario_status.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario_status.failed_stream, stream)
        self.assertIn("mass per year", scenario_status.failure_message)

    def assert_stream_fails_for_its_unit(self, stream, given):
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        with self.assertRaises(ImproperlyConfigured):
            run_inventory_stream.run(
                stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        scenario_status = ScenarioStatus.objects.get(scenario=self.scenario)
        self.assertEqual(scenario_status.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(scenario_status.failed_stream, stream)
        self.assertIn(given, scenario_status.failure_message)
        self.assertIn("mass per year", scenario_status.failure_message)
        self.assertFalse(Layer.objects.filter(stream=stream).exists())

    def test_stream_without_any_unit_fails(self):
        stream = self.count_stream()
        StreamFactor.objects.create(stream=stream, symbol="unit_yield", value=2.0)
        self.assert_stream_fails_for_its_unit(stream, "without a unit")

    def test_stream_that_yields_a_mass_without_time_fails(self):
        stream = self.direct_stream(base_unit="Mg")
        self.assert_stream_fails_for_its_unit(stream, "'Mg'")

    def test_share_in_percent_is_a_valid_factor(self):
        stream = self.count_stream()
        for order, (symbol, value, unit) in enumerate(
            (("unit_yield", 500.0, "kg / year"), ("share", 50.0, "percent"))
        ):
            StreamFactor.objects.create(
                stream=stream, symbol=symbol, value=value, unit=unit, order=order
            )
        layer = self.run_stream(stream)
        total = aggregated_value(layer, "Total production")
        self.assertAlmostEqual(total.value, 0.5)
        self.assertEqual(total.unit, "Mg/a")

    def test_run_inventory_plans_streams(self):
        stream = self.direct_stream()
        plan = self.scenario.stream_execution_plan()
        self.assertEqual([entry.id for entry in plan], [stream.id])


class AmountFilterTestCase(SimpleTestCase):
    def test_amount_keeps_decimals_without_trailing_zeros(self):
        for value, shown in (
            (0.7499999999999999, "0.75"),
            (23.8, "23.8"),
            (992.4, "992.4"),
            (3.0, "3"),
            (0, "0"),
            (0.00042, "0.00042"),
            (12345.6789, "12,345.679"),
            (None, "None"),
        ):
            with self.subTest(value=value):
                self.assertEqual(str(amount(value)), shown)


class StreamResultPageTestCase(StreamTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_user(username="stream-owner")
        cls.scenario.owner = cls.owner
        cls.scenario.save()

    def publish_layer(self):
        stream = self.yielding_count_stream()
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        run_inventory_stream.run(
            stream.id, scenario_id=self.scenario.id, run_id=str(run_id)
        )
        finalize_inventory.run(
            [True], self.scenario.id, str(run_id), [["stream", stream.id]]
        )
        return Layer.objects.get(stream=stream)

    def test_result_page_shows_the_stream_layer_and_links_its_map(self):
        layer = self.publish_layer()
        map_url = reverse(
            "scenario-result-layer-map",
            kwargs={"pk": self.scenario.pk, "layer_pk": layer.pk},
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.scenario.pk})
        )
        self.assertContains(response, "Number of features")
        self.assertContains(response, "Dataset: Greenhouses")
        self.assertContains(response, map_url)

        response = self.client.get(map_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Number of features")

    def test_result_page_reports_amounts_in_different_units(self):
        """Stored results of a mass and a mass per year are not added up."""
        per_year = self.direct_stream(name="Per year")
        mass = self.direct_stream(name="Mass only")
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        plan = [["stream", stream.id] for stream in (per_year, mass)]
        for _kind, stream_id in plan:
            run_inventory_stream.run(
                stream_id, scenario_id=self.scenario.id, run_id=str(run_id)
            )
        finalize_inventory.run([True, True], self.scenario.id, str(run_id), plan)
        # A mass without time can only be left from an earlier evaluation.
        Layer.objects.get(stream=mass).layeraggregatedvalue_set.filter(
            name="Total production"
        ).update(unit="Mg")
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.scenario.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "different units")
        self.assertNotIn("productionPerFeedstockBarChart", response.context["charts"])
        self.assertContains(response, "Mass only")

        # Stream results have no time steps; the summary is refused all the same.
        response = self.client.get(
            reverse(
                "scenario-download-result-summary",
                kwargs={"scenario_pk": self.scenario.pk},
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_result_page_shows_amounts_below_one_with_their_decimals(self):
        layer = self.publish_layer()
        layer.layeraggregatedvalue_set.filter(name="Total production").update(
            value=0.7499999999999999
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.scenario.pk})
        )
        self.assertContains(response, '<span class="sri-kpi-value">0.75</span>')

    def test_layer_map_is_hidden_from_other_users(self):
        layer = self.publish_layer()
        self.client.force_login(User.objects.create_user(username="stream-stranger"))
        response = self.client.get(
            reverse(
                "scenario-result-layer-map",
                kwargs={"pk": self.scenario.pk, "layer_pk": layer.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_failed_page_names_the_failed_stream(self):
        stream = self.direct_stream(name="Reported amount")
        self.set_status(ScenarioStatus.Status.FAILED, uuid4())
        scenario_status = self.scenario.scenariostatus
        scenario_status.failed_stream = stream
        scenario_status.save(update_fields=["failed_stream"])
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.scenario.pk})
        )
        self.assertContains(response, "Failed inventory: Reported amount")

    def test_progress_page_lists_running_streams(self):
        stream = self.direct_stream(name="Reported amount")
        run_id = uuid4()
        self.set_status(ScenarioStatus.Status.RUNNING, run_id)
        RunningTask.objects.create(
            scenario=self.scenario, uuid=uuid4(), stream=stream, run_id=run_id
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.scenario.pk})
        )
        self.assertContains(response, "Reported amount")
