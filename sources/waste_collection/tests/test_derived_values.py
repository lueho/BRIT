"""Tests for sources.waste_collection.derived_values."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import timezone

from maps.models import Region, RegionAttributeValue, RegionProperty
from maps.population.models import PopulationDataset, PopulationObservation
from utils.properties.models import Property, Unit

from ..derived_values import (
    backfill_derived_values,
    clear_derived_value_config_cache,
    compute_counterpart_value,
    convert_specific_to_total_mg,
    convert_total_to_specific,
    create_or_update_derived_cpv,
    delete_derived_cpv,
    get_derived_property_config,
    get_population_for_collection,
)
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from ..signals import sync_derived_cpv_on_delete, sync_derived_cpv_on_save
from ..waste_atlas.viewsets import (
    _amounts_for_2024,
    _resolved_population_attribute_id,
)


@override_settings(
    WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=None,
    WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID=None,
    WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID=None,
    WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID=None,
    WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID=None,
    WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [test]",
    WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_NAME="total waste collected [test]",
    WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [test]",
    WASTE_COLLECTION_TOTAL_WASTE_UNIT_NAME="Mg/a [test]",
    WASTE_COLLECTION_POPULATION_ATTRIBUTE_NAME="Population [test]",
)
class DerivedValuesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.property_specific = Property.objects.create(
            name="specific waste collected [test]"
        )
        cls.property_total = Property.objects.create(
            name="total waste collected [test]"
        )
        cls.unit_specific = Unit.objects.create(name="kg/(cap.*a) [test]")
        cls.unit_total = Unit.objects.create(name="Mg/a [test]")
        cls.population_attribute = RegionProperty.objects.create(
            name="Population [test]",
        )

        cls.collection_system = CollectionSystem.objects.create(
            name="Collection system"
        )
        cls.waste_category = WasteCategory.objects.create(name="Waste category")

    def setUp(self):
        clear_derived_value_config_cache()

    def tearDown(self):
        clear_derived_value_config_cache()

    def _create_collection(self, suffix, *, population=None):
        region = Region.objects.create(name=f"Region {suffix}", country="DE")
        catchment = CollectionCatchment.objects.create(
            name=f"Catchment {suffix}",
            region=region,
        )
        collection = Collection.objects.create(
            catchment=catchment,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        if population is not None:
            RegionAttributeValue.objects.create(
                name=f"Population {suffix}",
                region=region,
                property=self.population_attribute,
                date=date(2024, 1, 1),
                value=population,
            )
        return collection, catchment

    @staticmethod
    def _bulk_create_cpv(**kwargs):
        cpv = CollectionPropertyValue(**kwargs)
        CollectionPropertyValue.objects.bulk_create([cpv])
        return cpv

    def test_create_or_update_removes_stale_derived_when_manual_exists(self):
        collection, _catchment = self._create_collection("stale", population=2000)

        specific = self._bulk_create_cpv(
            name="specific source",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10,
            publication_status="published",
            is_derived=False,
        )

        _derived, action = create_or_update_derived_cpv(specific)
        self.assertEqual(action, "created")
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=True,
            ).exists()
        )

        self._bulk_create_cpv(
            name="manual total",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=25,
            publication_status="published",
            is_derived=False,
        )

        _derived, action = create_or_update_derived_cpv(specific)
        self.assertEqual(action, "skipped")
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=True,
            ).exists()
        )

    def test_backfill_counts_created_updated_and_skipped(self):
        collection_with_population, _ = self._create_collection(
            "has-pop", population=1000
        )
        collection_without_population, _ = self._create_collection(
            "no-pop", population=None
        )

        self._bulk_create_cpv(
            name="create-source",
            collection=collection_with_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="update-source",
            collection=collection_with_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2025,
            average=20,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="existing-derived-total",
            collection=collection_with_population,
            property=self.property_total,
            unit=self.unit_total,
            year=2025,
            average=20,
            publication_status="published",
            is_derived=True,
        )
        self._bulk_create_cpv(
            name="skip-manual-specific",
            collection=collection_with_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2026,
            average=30,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="manual-total",
            collection=collection_with_population,
            property=self.property_total,
            unit=self.unit_total,
            year=2026,
            average=30,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="skip-no-pop",
            collection=collection_without_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=40,
            publication_status="published",
            is_derived=False,
        )

        RegionAttributeValue.objects.create(
            name="Population has-pop 2025",
            region=collection_with_population.catchment.region,
            property=self.population_attribute,
            date=date(2025, 1, 1),
            value=1000,
        )

        dry_stats = backfill_derived_values(dry_run=True)
        self.assertEqual(dry_stats, {"created": 1, "updated": 1, "skipped": 3})

        write_stats = backfill_derived_values(dry_run=False)
        self.assertEqual(write_stats, {"created": 1, "updated": 1, "skipped": 3})

    def test_backfill_derives_counterpart_for_zero_value(self):
        collection, _ = self._create_collection("zero-backfill", population=1000)
        self._bulk_create_cpv(
            name="zero-source",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=0,
            publication_status="published",
            is_derived=False,
        )

        stats = backfill_derived_values()

        self.assertEqual(stats, {"created": 1, "updated": 0, "skipped": 0})
        derived = CollectionPropertyValue.objects.get(
            collection=collection,
            property=self.property_total,
            year=2024,
            is_derived=True,
        )
        self.assertEqual(derived.average, 0)

    def test_amounts_for_2024_falls_back_to_total_and_population(self):
        collection, catchment = self._create_collection(
            "atlas-fallback", population=2500
        )

        self._bulk_create_cpv(
            name="total-only",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=6.5,
            publication_status="published",
            is_derived=False,
        )

        amounts = _amounts_for_2024(
            year=2024,
            all_collection_ids={collection.pk},
            col_to_cid={collection.pk: catchment.pk},
            catchment_ids=[catchment.pk],
        )
        self.assertEqual(amounts[catchment.pk], 2.6)

    def test_amounts_for_2024_converts_zero_total_to_zero_specific(self):
        collection, catchment = self._create_collection(
            "atlas-zero-fallback", population=2500
        )
        self._bulk_create_cpv(
            name="zero-total-only",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=0,
            publication_status="published",
            is_derived=False,
        )

        amounts = _amounts_for_2024(
            year=2024,
            all_collection_ids={collection.pk},
            col_to_cid={collection.pk: catchment.pk},
            catchment_ids=[catchment.pk],
        )

        self.assertEqual(amounts[catchment.pk], 0)

    def test_amounts_fallback_does_not_use_population_from_another_year(self):
        collection, catchment = self._create_collection(
            "atlas-wrong-year", population=None
        )
        RegionAttributeValue.objects.create(
            name="Population atlas-wrong-year 2023",
            region=collection.catchment.region,
            property=self.population_attribute,
            date=date(2023, 1, 1),
            value=2500,
        )

        self._bulk_create_cpv(
            name="total-only-wrong-year",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=6.5,
            publication_status="published",
            is_derived=False,
        )

        amounts = _amounts_for_2024(
            year=2024,
            all_collection_ids={collection.pk},
            col_to_cid={collection.pk: catchment.pk},
            catchment_ids=[catchment.pk],
        )
        self.assertNotIn(catchment.pk, amounts)

    def test_compute_counterpart_value_returns_none_for_non_convertible_property(self):
        other_property = Property.objects.create(name="other property [test]")
        collection, _ = self._create_collection("other", population=1000)
        cpv = self._bulk_create_cpv(
            name="other-cpv",
            collection=collection,
            property=other_property,
            unit=self.unit_specific,
            year=2024,
            average=1.0,
            publication_status="published",
            is_derived=False,
        )
        self.assertIsNone(compute_counterpart_value(cpv))

    def test_compute_counterpart_value_returns_none_without_population(self):
        collection, _ = self._create_collection("no-pop-compute", population=None)
        cpv = self._bulk_create_cpv(
            name="specific-no-pop",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=12.3,
            publication_status="published",
            is_derived=False,
        )
        self.assertIsNone(compute_counterpart_value(cpv))

    def test_create_or_update_skips_when_input_is_already_derived(self):
        collection, _ = self._create_collection("already-derived", population=1000)
        derived_source = self._bulk_create_cpv(
            name="derived-source",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=True,
        )
        derived, action = create_or_update_derived_cpv(derived_source)
        self.assertIsNone(derived)
        self.assertEqual(action, "skipped")

    def test_conversion_helpers_guard_invalid_population(self):
        self.assertIsNone(convert_specific_to_total_mg(10, 0))
        self.assertIsNone(convert_specific_to_total_mg(10, -5))
        self.assertIsNone(convert_total_to_specific(10, 0))
        self.assertIsNone(convert_total_to_specific(10, -5))

    def test_get_derived_property_config_raises_for_invalid_configured_id(self):
        with override_settings(WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=999999):
            clear_derived_value_config_cache()
            with self.assertRaises(ImproperlyConfigured):
                get_derived_property_config()

    def test_get_derived_property_config_raises_for_ambiguous_names(self):
        Property.objects.create(name="specific waste collected [test]")
        with override_settings(WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=None):
            clear_derived_value_config_cache()
            with self.assertRaises(ImproperlyConfigured):
                get_derived_property_config()

    def test_signals_swallow_improperly_configured_and_do_not_raise(self):
        collection, _ = self._create_collection("signal-noise", population=1000)
        cpv = self._bulk_create_cpv(
            name="signal-cpv",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=15.0,
            publication_status="published",
            is_derived=False,
        )

        with override_settings(WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=999999):
            clear_derived_value_config_cache()
            # Should not raise; handler catches ImproperlyConfigured.
            sync_derived_cpv_on_save(sender=CollectionPropertyValue, instance=cpv)
            sync_derived_cpv_on_delete(sender=CollectionPropertyValue, instance=cpv)

    def test_population_attribute_resolution_uses_fallback_when_misconfigured(self):
        with override_settings(WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID=999999):
            clear_derived_value_config_cache()
            self.assertEqual(
                _resolved_population_attribute_id(), self.population_attribute.id
            )

    def test_convert_specific_to_total_mg_happy_path(self):
        self.assertEqual(convert_specific_to_total_mg(50, 2000), 100.0)
        self.assertEqual(convert_specific_to_total_mg(10, 500), 5.0)

    def test_convert_total_to_specific_happy_path(self):
        self.assertEqual(convert_total_to_specific(100, 2000), 50.0)
        self.assertEqual(convert_total_to_specific(5, 500), 10.0)

    def test_conversion_helpers_ndigits_none_returns_exact_decimal(self):
        result = convert_specific_to_total_mg(7, 3000, ndigits=None)
        self.assertEqual(result, Decimal("21"))
        result = convert_total_to_specific(7, 3000, ndigits=None)
        self.assertEqual(result, Decimal("7") * 1000 / Decimal("3000"))

    def test_conversion_helpers_respect_ndigits(self):
        self.assertEqual(
            convert_specific_to_total_mg(7, 3000, ndigits=1), Decimal("21.0")
        )
        self.assertEqual(
            convert_total_to_specific(6.5, 2500, ndigits=1), Decimal("2.6")
        )

    def test_conversion_helpers_accept_float_population_with_decimal_value(self):
        """Regression: float population from DB must not raise TypeError."""
        value = Decimal("50.0")
        self.assertEqual(convert_specific_to_total_mg(value, 2000.0), 100.0)
        self.assertEqual(convert_total_to_specific(value, 2000.0), 25.0)

    def test_compute_counterpart_specific_to_total(self):
        collection, _ = self._create_collection("s2t", population=5000)
        cpv = self._bulk_create_cpv(
            name="specific-s2t",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=80.0,
            publication_status="published",
            is_derived=False,
        )
        result = compute_counterpart_value(cpv)
        self.assertIsNotNone(result)
        target_prop_id, target_unit_id, computed = result
        self.assertEqual(target_prop_id, self.property_total.pk)
        self.assertEqual(target_unit_id, self.unit_total.pk)
        self.assertEqual(computed, 400.0)

    def test_compute_counterpart_total_to_specific(self):
        collection, _ = self._create_collection("t2s", population=4000)
        cpv = self._bulk_create_cpv(
            name="total-t2s",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=120.0,
            publication_status="published",
            is_derived=False,
        )
        result = compute_counterpart_value(cpv)
        self.assertIsNotNone(result)
        target_prop_id, target_unit_id, computed = result
        self.assertEqual(target_prop_id, self.property_specific.pk)
        self.assertEqual(target_unit_id, self.unit_specific.pk)
        self.assertEqual(computed, 30.0)

    def test_create_derived_total_stores_correct_average(self):
        collection, _ = self._create_collection("val-s2t", population=2000)
        cpv = self._bulk_create_cpv(
            name="source-specific",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=False,
        )
        derived, action = create_or_update_derived_cpv(cpv)
        self.assertEqual(action, "created")
        self.assertIsNotNone(derived)
        self.assertEqual(derived.average, 20.0)
        self.assertEqual(derived.property_id, self.property_total.pk)
        self.assertEqual(derived.unit_id, self.unit_total.pk)
        self.assertTrue(derived.is_derived)

    def test_create_derived_specific_from_total_stores_correct_average(self):
        collection, _ = self._create_collection("val-t2s", population=5000)
        cpv = self._bulk_create_cpv(
            name="source-total",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=250.0,
            publication_status="published",
            is_derived=False,
        )
        derived, action = create_or_update_derived_cpv(cpv)
        self.assertEqual(action, "created")
        self.assertIsNotNone(derived)
        self.assertEqual(derived.average, 50.0)
        self.assertEqual(derived.property_id, self.property_specific.pk)
        self.assertEqual(derived.unit_id, self.unit_specific.pk)
        self.assertTrue(derived.is_derived)

    def test_create_derived_review_value_copies_submitted_at(self):
        collection, _ = self._create_collection("review-meta", population=2000)
        submitted_at = timezone.now() - timedelta(days=1)
        cpv = self._bulk_create_cpv(
            name="source-review",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="review",
            submitted_at=submitted_at,
            is_derived=False,
        )
        derived, action = create_or_update_derived_cpv(cpv)
        self.assertEqual(action, "created")
        self.assertIsNotNone(derived)
        self.assertEqual(derived.publication_status, "review")
        self.assertEqual(derived.submitted_at, submitted_at)

    def test_create_or_update_updates_existing_derived_value(self):
        collection, _ = self._create_collection("update-val", population=1000)
        cpv = self._bulk_create_cpv(
            name="source-update",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=False,
        )
        derived1, action1 = create_or_update_derived_cpv(cpv)
        self.assertEqual(action1, "created")
        self.assertEqual(derived1.average, 10.0)

        cpv.average = 20.0
        cpv.save()
        derived2, action2 = create_or_update_derived_cpv(cpv)
        self.assertEqual(action2, "updated")
        self.assertEqual(derived2.average, 20.0)
        self.assertEqual(derived1.pk, derived2.pk)

    def test_delete_derived_cpv_removes_counterpart(self):
        collection, _ = self._create_collection("del", population=1000)
        source = self._bulk_create_cpv(
            name="source-del",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=False,
        )
        create_or_update_derived_cpv(source)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=True,
            ).exists()
        )

        count = delete_derived_cpv(source)
        self.assertEqual(count, 1)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=True,
            ).exists()
        )

    def test_delete_derived_cpv_does_not_remove_manual_counterpart(self):
        collection, _ = self._create_collection("del-manual", population=1000)
        source = self._bulk_create_cpv(
            name="source-del-m",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="manual-total",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=99.0,
            publication_status="published",
            is_derived=False,
        )

        count = delete_derived_cpv(source)
        self.assertEqual(count, 0)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=False,
            ).exists()
        )

    def test_delete_derived_cpv_skips_when_source_is_derived(self):
        collection, _ = self._create_collection("del-skip", population=1000)
        derived_source = self._bulk_create_cpv(
            name="derived-del",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=True,
        )
        self.assertEqual(delete_derived_cpv(derived_source), 0)

    def test_backfill_dry_run_does_not_write(self):
        collection, _ = self._create_collection("dryrun", population=1000)
        self._bulk_create_cpv(
            name="dry-source",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10.0,
            publication_status="published",
            is_derived=False,
        )
        derived_before = CollectionPropertyValue.objects.filter(is_derived=True).count()
        backfill_derived_values(dry_run=True)
        derived_after = CollectionPropertyValue.objects.filter(is_derived=True).count()
        self.assertEqual(derived_before, derived_after)

    def test_backfill_writes_correct_values(self):
        collection, _ = self._create_collection("bf-val", population=2000)
        RegionAttributeValue.objects.create(
            name="Population bf-val 2025",
            region=collection.catchment.region,
            property=self.population_attribute,
            date=date(2025, 1, 1),
            value=2000,
        )
        self._bulk_create_cpv(
            name="bf-specific",
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=60.0,
            publication_status="published",
            is_derived=False,
        )
        self._bulk_create_cpv(
            name="bf-total",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2025,
            average=50.0,
            publication_status="published",
            is_derived=False,
        )

        backfill_derived_values(dry_run=False)

        derived_total = CollectionPropertyValue.objects.get(
            collection=collection,
            property=self.property_total,
            year=2024,
            is_derived=True,
        )
        self.assertEqual(derived_total.average, 120.0)

        derived_specific = CollectionPropertyValue.objects.get(
            collection=collection,
            property=self.property_specific,
            year=2025,
            is_derived=True,
        )
        self.assertEqual(derived_specific.average, 25.0)

    def test_get_population_for_collection_returns_exact_year(self):
        collection, _ = self._create_collection("pop-year", population=None)
        region = collection.catchment.region
        RegionAttributeValue.objects.create(
            name="Pop 2023",
            region=region,
            property=self.population_attribute,
            date=date(2023, 1, 1),
            value=3000,
        )
        RegionAttributeValue.objects.create(
            name="Pop 2024",
            region=region,
            property=self.population_attribute,
            date=date(2024, 6, 15),
            value=3500,
        )
        self.assertEqual(get_population_for_collection(collection, year=2024), 3500)
        self.assertEqual(get_population_for_collection(collection, year=2023), 3000)

    def test_get_population_for_collection_never_falls_back_to_another_year(self):
        collection, _ = self._create_collection("pop-fallback", population=None)
        region = collection.catchment.region
        RegionAttributeValue.objects.create(
            name="Pop old",
            region=region,
            property=self.population_attribute,
            date=date(2020, 1, 1),
            value=1000,
        )
        RegionAttributeValue.objects.create(
            name="Pop newer",
            region=region,
            property=self.population_attribute,
            date=date(2022, 1, 1),
            value=2000,
        )
        self.assertIsNone(get_population_for_collection(collection, year=2024))
        self.assertIsNone(get_population_for_collection(collection))

    def test_get_population_for_collection_prefers_population_observation(self):
        collection, _ = self._create_collection("pop-observation", population=2000)
        region = collection.catchment.region
        dataset = PopulationDataset.objects.create(
            slug="eurostat-test",
            name="Eurostat test",
            provider="Eurostat",
            source_code="nama_10r_3popgdp",
            geographic_scope="nuts",
            temporal_basis="calendar_year_average",
            is_canonical=True,
        )
        PopulationObservation.objects.create(
            dataset=dataset,
            region=region,
            year=2024,
            value=Decimal("2500"),
        )
        self.assertEqual(
            get_population_for_collection(collection, year=2024), Decimal("2500")
        )
        self.assertIsNone(get_population_for_collection(collection, year=2023))

    def test_get_population_for_collection_returns_none_without_data(self):
        collection, _ = self._create_collection("pop-none", population=None)
        self.assertIsNone(get_population_for_collection(collection, year=2024))
