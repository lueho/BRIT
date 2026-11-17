"""Independently asserted numerical contracts for generated aggregates."""

import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from maps.models import NutsRegion
from maps.population.models import (
    GeographicScope,
    PopulationDataset,
    PopulationObservation,
    TemporalBasis,
)
from sources.waste_collection.derived_aggregates import (
    backfill_derived_acpvs,
    create_or_update_derived_acpv,
    delete_derived_acpv,
)
from sources.waste_collection.derived_values import clear_derived_value_config_cache
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.properties.models import Property, Unit
from utils.tests.testcases import ensure_test_default_owner


class GeneratedAggregateNumericalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls.owner = User.objects.create_user("agg-numeric-owner")
        cls.stranger = User.objects.create_user("agg-numeric-stranger")
        public = {"owner": cls.owner, "publication_status": "published"}
        cls.specific = Property.objects.create(name="agg numeric specific", **public)
        cls.total = Property.objects.create(name="agg numeric total", **public)
        cls.specific_unit = Unit.objects.create(name="agg numeric kg/cap/a", **public)
        cls.total_unit = Unit.objects.create(name="agg numeric Mg/a", **public)
        cls.system = CollectionSystem.objects.create(
            name="agg numeric system", **public
        )
        cls.category = WasteCategory.objects.create(
            name="agg numeric category", **public
        )
        cls.average_dataset = PopulationDataset.objects.create(
            slug="agg-numeric-annual-average",
            name="Synthetic aggregate annual-average population",
            provider="Synthetic test fixture",
            source_code="fixture-agg-annual-average",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.CALENDAR_YEAR_AVERAGE,
            source_unit="NR",
            classification_version="fixture-v1",
            is_canonical=True,
        )
        cls.stock_dataset = PopulationDataset.objects.create(
            slug="agg-numeric-point-in-time",
            name="Synthetic aggregate point-in-time stock",
            provider="Synthetic test fixture",
            source_code="fixture-agg-stock",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.POINT_IN_TIME,
            source_unit="NR",
            classification_version="fixture-v1",
            is_canonical=True,
        )
        cls.region = cls._nuts("agg numeric region one", "DTAAA")
        cls.region2 = cls._nuts("agg numeric region two", "DTBBB")
        cls.region_parent = cls._nuts("agg numeric parent", "DTAA")
        cls.observation = cls._observe(cls.region, 2024, "2000")
        cls.observation2 = cls._observe(cls.region2, 2024, "3000")
        cls.observation_parent = cls._observe(cls.region_parent, 2024, "4000")
        PopulationObservation.objects.create(
            dataset=cls.stock_dataset,
            region=cls.region,
            year=2024,
            value=Decimal("9999"),
        )
        cls.catchment = cls._catchment("agg numeric catchment", cls.region)
        cls.catchment2 = cls._catchment("agg numeric catchment two", cls.region2)
        cls.catchment_parent = cls._catchment(
            "agg numeric parent catchment", cls.region_parent
        )
        cls.catchment_no_region = cls._catchment("agg numeric unmapped catchment", None)
        cls.collection = cls._collection("one", cls.catchment)
        cls.collection2 = cls._collection("two", cls.catchment2)
        cls.collection_overlap = cls._collection("overlap", cls.catchment_parent)
        cls.collection_parallel = cls._collection("parallel", cls.catchment)
        cls.collection_no_region = cls._collection("no-region", cls.catchment_no_region)
        cls.collection_no_catchment = cls._collection("no-catchment", None)

    @classmethod
    def _nuts(cls, name, nuts_id):
        return NutsRegion.objects.create(
            name=name, levl_code=3, cntr_code="DT", nuts_id=nuts_id
        )

    @classmethod
    def _observe(cls, region, year, value):
        return PopulationObservation.objects.create(
            dataset=cls.average_dataset,
            region=region,
            year=year,
            value=Decimal(value),
        )

    @classmethod
    def _catchment(cls, name, region):
        return CollectionCatchment.objects.create(
            name=name, region=region, publication_status="published"
        )

    @classmethod
    def _collection(cls, suffix, catchment):
        return Collection.objects.create(
            name=f"agg numeric collection {suffix}",
            publication_status="published",
            catchment=catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
        )

    def setUp(self):
        self.config = self.settings(
            WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=self.specific.pk,
            WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID=self.total.pk,
            WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID=self.specific_unit.pk,
            WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID=self.total_unit.pk,
        )
        self.config.enable()
        clear_derived_value_config_cache()
        self.addCleanup(self.config.disable)
        self.addCleanup(clear_derived_value_config_cache)

    def _raw(
        self,
        prop,
        unit,
        average,
        collections,
        *,
        owner=None,
        state="private",
        year=2024,
    ):
        """Persist a reported aggregate without firing generation signals."""
        row = AggregatedCollectionPropertyValue(
            property=prop,
            unit=unit,
            average=Decimal(average),
            year=year,
            owner=owner or self.owner,
            publication_status=state,
            is_derived=False,
        )
        AggregatedCollectionPropertyValue.objects.bulk_create([row])
        through = AggregatedCollectionPropertyValue.collections.through
        through.objects.bulk_create(
            [
                through(
                    aggregatedcollectionpropertyvalue_id=row.pk,
                    collection_id=collection.pk,
                )
                for collection in collections
            ]
        )
        return row

    def _assert_output(self, source, prop, unit, average, population):
        raw_fields = (
            "average",
            "standard_deviation",
            "unit_id",
            "property_id",
            "year",
            "owner_id",
            "publication_status",
            "content_revision",
        )
        raw_before = AggregatedCollectionPropertyValue.objects.values(*raw_fields).get(
            pk=source.pk
        )
        generated, action = create_or_update_derived_acpv(source)
        self.assertIn(action, {"created", "updated"})
        self.assertEqual(
            AggregatedCollectionPropertyValue.objects.values(*raw_fields).get(
                pk=source.pk
            ),
            raw_before,
        )
        generated.refresh_from_db()
        self.assertEqual(getattr(generated, "derived_from_id", None), source.pk)
        self.assertTrue(generated.is_derived)
        self.assertEqual(
            set(generated.collections.values_list("pk", flat=True)),
            set(source.collections.values_list("pk", flat=True)),
        )
        self.assertEqual(generated.year, source.year)
        self.assertEqual(generated.property_id, prop.pk)
        self.assertEqual(generated.unit_id, unit.pk)
        self.assertEqual(Decimal(str(generated.average)), Decimal(average))
        self.assertIsNone(generated.standard_deviation)
        self.assertEqual(generated.owner_id, source.owner_id)
        self.assertEqual(generated.publication_status, source.publication_status)
        for field in ("submitted_at", "approved_at", "approved_by_id"):
            self.assertEqual(getattr(generated, field), getattr(source, field))
        description = json.loads(generated.description)
        self.assertEqual(description["source_acpv"]["id"], source.pk)
        self.assertEqual(description["source_acpv"]["unit_id"], source.unit_id)
        self.assertEqual(
            Decimal(description["source_acpv"]["average"]),
            Decimal(str(raw_before["average"])),
        )
        self.assertEqual(
            Decimal(description["population"]["value"]), Decimal(str(population))
        )
        self.assertEqual(description["population"]["year"], 2024)
        self.assertEqual(
            description["population"]["temporal_basis"],
            TemporalBasis.CALENDAR_YEAR_AVERAGE,
        )
        return generated

    def test_conversion_directions_preserve_numeric_contract(self):
        cases = [
            (
                self.specific,
                self.specific_unit,
                "150",
                self.total,
                self.total_unit,
                "300",
            ),
            (
                self.total,
                self.total_unit,
                "300",
                self.specific,
                self.specific_unit,
                "150",
            ),
        ]
        for prop, unit, amount, target_prop, target_unit, expected in cases:
            with self.subTest(property=prop.name, amount=amount):
                source = self._raw(prop, unit, amount, [self.collection])
                self._assert_output(source, target_prop, target_unit, expected, 2000)

    def test_multi_region_denominator_sums_distinct_regions(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection, self.collection2],
        )
        generated = self._assert_output(
            source, self.total, self.total_unit, "750", 5000
        )
        description = json.loads(generated.description)
        self.assertEqual(description["population"]["method"], "summed")
        self.assertFalse(description["population"]["is_provisional"])
        self.assertFalse(description["population"]["is_mixed_provenance"])
        observation_ids = {
            observation["id"]
            for observation in description["population"]["observations"]
        }
        self.assertEqual(observation_ids, {self.observation.pk, self.observation2.pk})

    def test_multi_region_denominator_converts_total_to_specific(self):
        source = self._raw(
            self.total,
            self.total_unit,
            "750",
            [self.collection, self.collection2],
        )
        self._assert_output(source, self.specific, self.specific_unit, "150", 5000)

    def test_parallel_services_share_region_once(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection, self.collection_parallel],
        )
        self._assert_output(source, self.total, self.total_unit, "300", 2000)

    def test_overlapping_regions_fail_closed_without_output(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection, self.collection_overlap],
        )
        with self.assertLogs(
            "sources.waste_collection.derived_aggregates", level="WARNING"
        ) as logged:
            output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")
        self.assertFalse(source.generated_values.exists())
        self.assertIn("region", "\n".join(logged.output).lower())

    def test_member_without_region_fails_closed(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection, self.collection_no_region],
        )
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")
        self.assertFalse(source.generated_values.exists())

    def test_member_without_catchment_fails_closed(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection_no_catchment],
        )
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")

    def test_empty_membership_fails_closed(self):
        source = self._raw(self.specific, self.specific_unit, "150", [])
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")

    def test_missing_exact_year_population_fails_without_inventing(self):
        source = self._raw(
            self.specific, self.specific_unit, "150", [self.collection], year=2023
        )
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")

    def test_stock_only_population_does_not_substitute(self):
        stock_region = type(self)._nuts("agg stock region", "DTCCC")
        PopulationObservation.objects.create(
            dataset=self.stock_dataset,
            region=stock_region,
            year=2024,
            value=Decimal("8888"),
        )
        stock_catchment = type(self)._catchment("agg stock catchment", stock_region)
        stock_collection = type(self)._collection("stock", stock_catchment)
        source = self._raw(self.specific, self.specific_unit, "150", [stock_collection])
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")

    def test_wrong_unit_or_unconvertible_property_fails_safely(self):
        wrong_unit = self._raw(self.specific, self.total_unit, "150", [self.collection])
        other_property = Property.objects.create(
            name="agg numeric other", owner=self.owner
        )
        unconvertible = self._raw(
            other_property, self.specific_unit, "150", [self.collection]
        )
        for source in (wrong_unit, unconvertible):
            with self.subTest(source=source.pk):
                output, action = create_or_update_derived_acpv(source)
                self.assertIsNone(output)
                self.assertEqual(action, "skipped")
                self.assertFalse(source.generated_values.exists())

    def test_derived_source_is_rejected_as_input(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        generated = self._assert_output(
            source, self.total, self.total_unit, "300", 2000
        )
        output, action = create_or_update_derived_acpv(generated)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")

    def test_generation_is_idempotent_and_metadata_only_refresh(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        first = self._assert_output(source, self.total, self.total_unit, "300", 2000)
        second = self._assert_output(source, self.total, self.total_unit, "300", 2000)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(source.generated_values.count(), 1)

    def test_membership_change_recomputes_denominator(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        generated = self._assert_output(
            source, self.total, self.total_unit, "300", 2000
        )
        source.collections.add(self.collection2)
        generated.refresh_from_db()
        self.assertEqual(Decimal(str(generated.average)), Decimal("750"))
        self.assertEqual(
            set(generated.collections.values_list("pk", flat=True)),
            {self.collection.pk, self.collection2.pk},
        )
        source.collections.remove(self.collection2)
        generated.refresh_from_db()
        self.assertEqual(Decimal(str(generated.average)), Decimal("300"))

    def test_raw_save_signal_generates_end_to_end(self):
        source = AggregatedCollectionPropertyValue.objects.create(
            property=self.specific,
            unit=self.specific_unit,
            average=150,
            year=2024,
            owner=self.owner,
            publication_status="private",
        )
        self.assertFalse(source.generated_values.exists())
        source.collections.set([self.collection])
        generated = source.generated_values.get()
        self.assertTrue(generated.is_derived)
        self.assertEqual(generated.derived_from_id, source.pk)
        self.assertEqual(Decimal(str(generated.average)), Decimal("300"))

    def test_ineligible_source_invalidates_only_own_output(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        other = self._raw(self.specific, self.specific_unit, "175", [self.collection2])
        first = self._assert_output(source, self.total, self.total_unit, "300", 2000)
        second = self._assert_output(other, self.total, self.total_unit, "525", 3000)
        manual = self._raw(self.total, self.total_unit, "400", [self.collection])
        AggregatedCollectionPropertyValue.objects.filter(pk=source.pk).update(
            unit=self.total_unit
        )
        output, action = create_or_update_derived_acpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(pk=first.pk).exists()
        )
        second.refresh_from_db()
        self.assertEqual(Decimal(str(second.average)), Decimal("525"))
        manual.refresh_from_db()
        self.assertFalse(manual.is_derived)
        self.assertIsNone(manual.derived_from_id)

    def test_delete_derived_acpv_removes_only_linked_output(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        other = self._raw(self.specific, self.specific_unit, "175", [self.collection2])
        first = self._assert_output(source, self.total, self.total_unit, "300", 2000)
        second = self._assert_output(other, self.total, self.total_unit, "525", 3000)
        manual = self._raw(self.total, self.total_unit, "400", [self.collection])
        self.assertEqual(delete_derived_acpv(source), 1)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(pk=first.pk).exists()
        )
        second.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(delete_derived_acpv(first), 0)
        self.assertTrue(
            AggregatedCollectionPropertyValue.objects.filter(pk=second.pk).exists()
        )

    def test_dry_run_and_real_backfill_agree(self):
        valid = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        invalid = self._raw(self.specific, self.total_unit, "150", [self.collection])
        before = set(
            AggregatedCollectionPropertyValue.objects.values_list("pk", flat=True)
        )
        expected = {"created": 1, "updated": 0, "skipped": 1}
        self.assertEqual(backfill_derived_acpvs(dry_run=True), expected)
        self.assertEqual(
            set(AggregatedCollectionPropertyValue.objects.values_list("pk", flat=True)),
            before,
        )
        self.assertEqual(backfill_derived_acpvs(), expected)
        self.assertEqual(valid.generated_values.get().average, 300)
        self.assertFalse(invalid.generated_values.exists())

    def test_reported_aggregate_lifecycle_is_preserved(self):
        source = self._raw(
            self.total, self.total_unit, "400", [self.collection], state="private"
        )
        self.assertFalse(source.is_derived)
        self.assertIsNone(source.derived_from_id)
        source.average = 450
        source.save()
        source.refresh_from_db()
        self.assertEqual(source.average, 450)
        self.assertFalse(source.is_derived)

    def test_copied_metadata_does_not_grant_or_fabricate(self):
        source = self._raw(self.specific, self.specific_unit, "150", [self.collection])
        generated, action = create_or_update_derived_acpv(
            source, owner=self.stranger, publication_status="published"
        )
        self.assertEqual(action, "created")
        generated.refresh_from_db()
        self.assertEqual(generated.owner_id, self.stranger.pk)
        self.assertEqual(generated.publication_status, "published")
        self.assertIsNone(generated.approved_at)
        self.assertIsNone(generated.approved_by_id)
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "private")
        self.assertIsNone(source.approved_at)
