"""Tests for sources.waste_collection.derived_values."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from maps.models import Region, RegionAttributeValue, RegionProperty
from maps.population.models import PopulationDataset, PopulationObservation
from utils.object_management.models import ReviewAction
from utils.object_management.policy import scope_queryset
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
    preferred_measurement_queryset,
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

    def test_manual_counterpart_does_not_block_generated_artifact(self):
        """Manual evidence coexists with — and never deletes — the artifact."""
        collection, _ = self._create_collection("manual-coexist", population=2000)

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

        derived, action = create_or_update_derived_cpv(specific)
        self.assertEqual(action, "created")
        self.assertEqual(derived.average, 20.0)
        self.assertEqual(derived.derived_from_id, specific.pk)

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

        derived, action = create_or_update_derived_cpv(specific)
        self.assertEqual(action, "updated")
        self.assertEqual(derived.average, 20.0)
        self.assertEqual(derived.derived_from_id, specific.pk)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                collection=collection,
                property=self.property_total,
                year=2024,
                is_derived=False,
                average=25,
            ).exists()
        )

    def test_backfill_counts_created_updated_and_skipped(self):
        """Contract counts: created, updated, and skipped sources.

        A manual counterpart at the same key never skips a valid source, and
        a legacy unlinked derived row never counts as a source's output.
        """
        collection_with_population, _ = self._create_collection(
            "has-pop", population=1000
        )
        collection_without_population, _ = self._create_collection(
            "no-pop", population=None
        )

        create_source = self._bulk_create_cpv(
            name="create-source",
            collection=collection_with_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10,
            publication_status="published",
            is_derived=False,
        )
        update_source = self._bulk_create_cpv(
            name="update-source",
            collection=collection_with_population,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2025,
            average=20,
            publication_status="published",
            is_derived=False,
        )
        # Legacy orphan at the same key is never adopted as linked output.
        orphan = self._bulk_create_cpv(
            name="legacy-orphan-total",
            collection=collection_with_population,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=99,
            publication_status="published",
            is_derived=True,
            derived_from=None,
        )
        # Manual counterpart at the source's output key neither blocks nor
        # skips it; the manual row itself is a valid source too.
        manual = self._bulk_create_cpv(
            name="manual-total",
            collection=collection_with_population,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
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

        # update-source keeps an explicitly linked artifact; the orphan does
        # not satisfy the "updated" category for create-source.
        _linked, action = create_or_update_derived_cpv(update_source)
        self.assertEqual(action, "created")

        dry_stats = backfill_derived_values(dry_run=True)
        # create-source and manual-total each gain a linked artifact;
        # update-source refreshes its existing one; no-pop is skipped.
        self.assertEqual(dry_stats, {"created": 2, "updated": 1, "skipped": 1})

        write_stats = backfill_derived_values(dry_run=False)
        self.assertEqual(write_stats, {"created": 2, "updated": 1, "skipped": 1})

        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=create_source
            ).exists()
        )
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=manual
            ).exists()
        )
        orphan.refresh_from_db()
        self.assertIsNone(orphan.derived_from_id)

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

    # --- Phase B1: explicit source-bound generation --------------------------

    def _create_source(self, collection, **kwargs):
        """Create a raw CPV through the manager so save signals run."""
        kwargs.setdefault("name", "raw source")
        kwargs.setdefault("property", self.property_specific)
        kwargs.setdefault("unit", self.unit_specific)
        kwargs.setdefault("year", 2024)
        kwargs.setdefault("publication_status", "published")
        kwargs["is_derived"] = False
        return CollectionPropertyValue.objects.create(collection=collection, **kwargs)

    def test_generated_artifact_links_its_source(self):
        collection, _ = self._create_collection("link-s2t", population=2000)
        source = self._create_source(collection, average=10)

        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )
        self.assertEqual(artifact.average, Decimal("20.00"))
        self.assertEqual(artifact.property_id, self.property_total.pk)
        self.assertEqual(artifact.unit_id, self.unit_total.pk)
        self.assertEqual(artifact.collection_id, collection.pk)
        self.assertEqual(artifact.year, 2024)

    def test_total_source_generates_linked_specific_artifact(self):
        collection, _ = self._create_collection("link-t2s", population=2000)
        source = self._create_source(
            collection,
            property=self.property_total,
            unit=self.unit_total,
            average=10,
        )

        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )
        self.assertEqual(artifact.average, Decimal("5.00"))
        self.assertEqual(artifact.property_id, self.property_specific.pk)
        self.assertEqual(artifact.unit_id, self.unit_specific.pk)

    def test_two_sources_same_key_keep_separate_artifacts(self):
        collection, _ = self._create_collection("two-src", population=2000)
        source1 = self._create_source(collection, average=10)
        artifact1 = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source1
        )
        artifact1_pk, artifact1_average, artifact1_owner = (
            artifact1.pk,
            artifact1.average,
            artifact1.owner_id,
        )

        source2 = self._create_source(collection, average=20)
        artifact2 = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source2
        )

        self.assertNotEqual(artifact1.pk, artifact2.pk)
        self.assertEqual(artifact1.average, Decimal("20.00"))
        self.assertEqual(artifact2.average, Decimal("40.00"))
        # Creating source2 never touches source1's artifact.
        artifact1.refresh_from_db()
        self.assertEqual(
            (artifact1.pk, artifact1.average, artifact1.owner_id),
            (artifact1_pk, artifact1_average, artifact1_owner),
        )

    def test_source_lifecycle_governs_artifact_visibility(self):
        collection, _ = self._create_collection("scope", population=2000)
        published_source = self._create_source(collection, average=10)
        private_source = self._create_source(
            collection, year=2024, publication_status="private", average=10
        )
        artifact_published = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=published_source
        )
        artifact_private = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=private_source
        )

        public_qs = scope_queryset(
            AnonymousUser(),
            CollectionPropertyValue.objects.all(),
            "published",
        )
        self.assertIn(artifact_published, public_qs)
        self.assertNotIn(artifact_private, public_qs)

    def test_source_edit_updates_only_its_own_artifact(self):
        collection, _ = self._create_collection("edit-src", population=2000)
        source1 = self._create_source(collection, average=10)
        source2 = self._create_source(collection, average=20)
        artifact1 = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source1
        )
        artifact2 = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source2
        )

        source1.average = 15
        source1.save()

        artifact1.refresh_from_db()
        artifact2.refresh_from_db()
        self.assertEqual(artifact1.average, Decimal("30.00"))
        self.assertEqual(artifact2.average, Decimal("40.00"))

    def test_source_becoming_non_convertible_removes_its_artifact(self):
        collection, _ = self._create_collection("non-conv", population=2000)
        other_property = Property.objects.create(name="other property [test]")
        source = self._create_source(collection, average=10)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=source
            ).exists()
        )

        source.property = other_property
        source.save()

        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=source
            ).exists()
        )

    def test_source_losing_population_removes_its_artifact(self):
        collection, _ = self._create_collection("no-pop-edit", population=2000)
        source = self._create_source(collection, average=10)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=source
            ).exists()
        )

        # 2026 has no exact-year population for this region.
        source.year = 2026
        source.save()

        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=source
            ).exists()
        )

    def test_source_delete_removes_only_its_own_artifact(self):
        collection, _ = self._create_collection("del-own", population=2000)
        source1 = self._create_source(collection, average=10)
        source2 = self._create_source(collection, average=20)
        manual = self._bulk_create_cpv(
            name="manual total",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=25,
            publication_status="published",
            is_derived=False,
        )
        orphan = self._bulk_create_cpv(
            name="legacy orphan",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2025,
            average=99,
            publication_status="published",
            is_derived=True,
            derived_from=None,
        )
        artifact2 = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source2
        )
        source1_pk = source1.pk

        source1.delete()

        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from_id=source1_pk
            ).exists()
        )
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=artifact2.pk).exists()
        )
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=manual.pk).exists())
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=orphan.pk).exists())

    def test_source_delete_rolls_back_when_sync_fails(self):
        collection, _ = self._create_collection("del-rb", population=2000)
        source = self._create_source(collection, average=10)
        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )

        with (
            self.assertLogs("sources.waste_collection.signals", level="ERROR"),
            self.assertRaises(RuntimeError),
            transaction.atomic(),
        ):
            with patch(
                "sources.waste_collection.derived_values.delete_derived_cpv",
                side_effect=RuntimeError("boom"),
            ):
                source.delete()

        self.assertTrue(CollectionPropertyValue.objects.filter(pk=source.pk).exists())
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=artifact.pk).exists())

    def test_save_failure_rolls_back_source_and_artifact(self):
        collection, _ = self._create_collection("save-rb", population=2000)
        source = self._create_source(collection, average=10)
        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )

        with (
            self.assertLogs("sources.waste_collection.signals", level="ERROR"),
            self.assertRaises(RuntimeError),
            transaction.atomic(),
        ):
            with patch(
                "sources.waste_collection.derived_values.create_or_update_derived_cpv",
                side_effect=RuntimeError("boom"),
            ):
                source.average = 15
                source.save()

        source.refresh_from_db()
        artifact.refresh_from_db()
        self.assertEqual(source.average, 10)
        self.assertEqual(artifact.average, Decimal("20.00"))

    def test_missing_config_with_linked_output_denies_source_save(self):
        collection, _ = self._create_collection("misconf", population=2000)
        source = self._create_source(collection, average=10)
        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )

        with override_settings(WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=999999):
            clear_derived_value_config_cache()
            with (
                self.assertRaises(ImproperlyConfigured),
                transaction.atomic(),
            ):
                source.average = 15
                source.save()
        clear_derived_value_config_cache()

        source.refresh_from_db()
        artifact.refresh_from_db()
        self.assertEqual(source.average, 10)
        self.assertEqual(artifact.average, Decimal("20.00"))

    def test_recompute_creates_no_review_events(self):
        collection, _ = self._create_collection("no-events", population=2000)
        source = self._create_source(collection, average=10)
        artifact = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )
        ct = ContentType.objects.get_for_model(CollectionPropertyValue)

        source.average = 15
        source.save()
        create_or_update_derived_cpv(source)

        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ct, object_id__in=(source.pk, artifact.pk)
            ).exists()
        )

    def test_unsaved_or_generated_input_is_skipped(self):
        collection, _ = self._create_collection("skip-input", population=2000)
        unsaved = CollectionPropertyValue(
            collection=collection,
            property=self.property_specific,
            unit=self.unit_specific,
            year=2024,
            average=10,
            is_derived=False,
        )
        self.assertEqual(create_or_update_derived_cpv(unsaved), (None, "skipped"))

        generated = self._bulk_create_cpv(
            name="generated",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=5,
            is_derived=True,
        )
        self.assertEqual(create_or_update_derived_cpv(generated), (None, "skipped"))

    def test_delete_derived_cpv_removes_only_linked_output(self):
        collection, _ = self._create_collection("del-linked", population=2000)
        source = self._create_source(collection, average=10)
        CollectionPropertyValue.objects.get(is_derived=True, derived_from=source)

        self.assertEqual(delete_derived_cpv(source), 1)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                is_derived=True, derived_from=source
            ).exists()
        )

    # --- Phase B1: purpose-scoped manual precedence -------------------------

    def test_preferred_measurement_keeps_manual_over_generated(self):
        collection, _ = self._create_collection("pref", population=2000)
        source = self._create_source(collection, average=10)
        generated = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )
        manual = self._bulk_create_cpv(
            name="manual total 25",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=25,
            is_derived=False,
        )

        preferred = preferred_measurement_queryset(
            CollectionPropertyValue.objects.filter(collection=collection)
        )
        self.assertIn(source, preferred)
        self.assertIn(manual, preferred)
        self.assertNotIn(generated, preferred)

    def test_preferred_measurement_requires_matching_year_and_unit(self):
        collection, _ = self._create_collection("pref-key", population=2000)
        source = self._create_source(collection, average=10)
        generated = CollectionPropertyValue.objects.get(
            is_derived=True, derived_from=source
        )
        other_year_manual = self._bulk_create_cpv(
            name="manual other year",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2025,
            average=25,
            is_derived=False,
        )
        other_unit_manual = self._bulk_create_cpv(
            name="manual other unit",
            collection=collection,
            property=self.property_total,
            unit=self.unit_specific,
            year=2024,
            average=25,
            is_derived=False,
        )

        preferred = preferred_measurement_queryset(
            CollectionPropertyValue.objects.filter(collection=collection)
        )
        self.assertIn(generated, preferred)
        self.assertIn(other_year_manual, preferred)
        self.assertIn(other_unit_manual, preferred)

    def test_preferred_measurement_null_year_matches_null_only(self):
        collection, _ = self._create_collection("pref-null", population=2000)
        null_year_generated = self._bulk_create_cpv(
            name="generated null year",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=None,
            average=20,
            is_derived=True,
        )
        null_year_manual = self._bulk_create_cpv(
            name="manual null year",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=None,
            average=25,
            is_derived=False,
        )
        different_year_manual = self._bulk_create_cpv(
            name="manual different year",
            collection=collection,
            property=self.property_total,
            unit=self.unit_total,
            year=2024,
            average=30,
            is_derived=False,
        )

        preferred = preferred_measurement_queryset(
            CollectionPropertyValue.objects.filter(
                collection=collection, property=self.property_total
            )
        )
        # A null-year manual suppresses only a matching null-year generated row.
        self.assertNotIn(null_year_generated, preferred)
        self.assertIn(null_year_manual, preferred)
        self.assertIn(different_year_manual, preferred)

        different_year_manual.delete()
        null_year_manual.delete()
        preferred = preferred_measurement_queryset(
            CollectionPropertyValue.objects.filter(
                collection=collection, property=self.property_total
            )
        )
        self.assertIn(null_year_generated, preferred)
