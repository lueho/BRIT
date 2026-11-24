"""Tests for the declarative stream evaluator."""

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from inventories.algorithms import InventoryAlgorithms
from inventories.evaluator import (
    BaseKind,
    Condition,
    StreamSpec,
    Term,
    evaluate,
)
from maps.models import Catchment, GeoDataset, Region
from sources.greenhouses.models import NantesGreenhouses

CATCHMENT = MultiPolygon(
    Polygon(((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)), srid=4326), srid=4326
)


def aggregated_value(result, name):
    return next(entry for entry in result["aggregated_values"] if entry["name"] == name)


class DirectEntryTestCase(TestCase):
    """A directly entered amount needs no dataset at all."""

    def test_amount_times_factor_chain(self):
        spec = StreamSpec(
            base_kind=BaseKind.DIRECT,
            base=Term("amount", 1200.0, unit="kg / year"),
            factors=(Term("collection_share", 0.5),),
        )
        result = evaluate(spec, CATCHMENT)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], 0.6)
        self.assertEqual(production["unit"], "Mg/a")

    def test_catchment_is_the_only_feature(self):
        spec = StreamSpec(
            base_kind=BaseKind.DIRECT, base=Term("amount", 2.0, unit="Mg / year")
        )
        result = evaluate(spec, CATCHMENT)
        self.assertEqual(result["geom_type"], "MultiPolygon")
        self.assertEqual(len(result["features"]), 1)
        self.assertTrue(result["features"][0]["geom"].equals(CATCHMENT))
        self.assertAlmostEqual(result["features"][0]["production"], 2.0)

    def test_base_uncertainty_combines_with_factor_uncertainty(self):
        spec = StreamSpec(
            base_kind=BaseKind.DIRECT,
            base=Term("amount", 100.0, standard_deviation=10.0, unit="Mg / year"),
            factors=(Term("share", 0.5, standard_deviation=0.05),),
        )
        result = evaluate(spec, CATCHMENT)
        deviation = aggregated_value(result, "Total production standard deviation")
        # sqrt((10 * 0.5)^2 + (100 * 0.05)^2)
        self.assertAlmostEqual(deviation["value"], 50**0.5)

    def test_missing_amount_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            evaluate(StreamSpec(base_kind=BaseKind.DIRECT), CATCHMENT)


class DatasetBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Evaluator Region", country="DE")
        cls.region.geom = CATCHMENT
        cls.region.save()
        cls.catchment = Catchment.objects.create(name="Evaluator", region=cls.region)
        cls.dataset = GeoDataset.objects.create(
            name="Greenhouses", region=cls.region, model_name="NantesGreenhouses"
        )
        rows = (
            (0.5, 0.5, "Tomato", True, 2.0),
            (-0.5, 0.2, "Cucumber", True, 3.0),
            (0.1, 0.1, "Tomato", False, 5.0),
            (5, 5, "Tomato", True, 7.0),
        )
        for x, y, culture, heated, surface in rows:
            NantesGreenhouses.objects.create(
                geom=Point(x, y, srid=4326),
                culture_1=culture,
                heated=heated,
                surface_ha=surface,
            )

    def spec(self, **kwargs):
        kwargs.setdefault("base_kind", BaseKind.FEATURE_COUNT)
        return StreamSpec(geodataset=self.dataset, **kwargs)

    def test_count_matches_legacy_generic_function(self):
        factors = (Term("unit_yield", 25.0, 2.5, "kg / year"), Term("share", 0.5))
        result = evaluate(self.spec(factors=factors), CATCHMENT)
        legacy = InventoryAlgorithms.count_based_production(
            geodataset_id=self.dataset.id,
            catchment_id=self.catchment.id,
            unit_yield={"value": 25.0, "standard_deviation": 2.5, "unit": "kg / year"},
            share={"value": 0.5},
        )
        self.assertEqual(result["aggregated_values"], legacy["aggregated_values"])
        self.assertEqual(len(result["features"]), len(legacy["features"]))

    def test_several_conditions_are_combined(self):
        spec = self.spec(
            filters=(
                Condition("culture_1", "eq", "Tomato"),
                Condition("heated", "eq", "True"),
            )
        )
        self.assertEqual(
            aggregated_value(evaluate(spec, CATCHMENT), "Count")["value"], 1
        )

    def test_in_condition_matches_any_listed_value(self):
        spec = self.spec(filters=(Condition("culture_1", "in", "Tomato, Cucumber"),))
        self.assertEqual(
            aggregated_value(evaluate(spec, CATCHMENT), "Count")["value"], 3
        )

    def test_not_equal_condition(self):
        spec = self.spec(filters=(Condition("culture_1", "ne", "Tomato"),))
        self.assertEqual(
            aggregated_value(evaluate(spec, CATCHMENT), "Count")["value"], 1
        )

    def test_range_conditions(self):
        spec = self.spec(
            filters=(
                Condition("surface_ha", "gte", "3"),
                Condition("surface_ha", "lte", "5"),
            )
        )
        self.assertEqual(
            aggregated_value(evaluate(spec, CATCHMENT), "Count")["value"], 2
        )

    def test_unknown_operator_is_rejected(self):
        spec = self.spec(filters=(Condition("culture_1", "like", "Tom"),))
        with self.assertRaises(ImproperlyConfigured):
            evaluate(spec, CATCHMENT)

    def test_column_sum_adds_attribute_of_features_in_catchment(self):
        spec = self.spec(
            base_kind=BaseKind.COLUMN_SUM,
            base_column="surface_ha",
            base_unit="hectare",
            factors=(Term("area_yield", 10.0, unit="Mg / hectare / year"),),
        )
        result = evaluate(spec, CATCHMENT)
        self.assertAlmostEqual(aggregated_value(result, "Sum")["value"], 10.0)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], 100.0)
        self.assertEqual(production["unit"], "Mg/a")
        self.assertEqual(
            sorted(feature["production"] for feature in result["features"]),
            [20.0, 30.0, 50.0],
        )

    def test_column_sum_requires_a_column(self):
        with self.assertRaises(ImproperlyConfigured):
            evaluate(self.spec(base_kind=BaseKind.COLUMN_SUM), CATCHMENT)

    def test_dataset_base_requires_a_dataset(self):
        with self.assertRaises(ImproperlyConfigured):
            evaluate(StreamSpec(base_kind=BaseKind.FEATURE_COUNT), CATCHMENT)
