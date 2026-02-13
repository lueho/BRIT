from datetime import date

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from case_studies.soilcom.derived_values import (
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
from case_studies.soilcom.models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)
from case_studies.soilcom.signals import (
    sync_derived_cpv_on_delete,
    sync_derived_cpv_on_save,
)
from case_studies.soilcom.waste_atlas.viewsets import (
    POPULATION_ATTRIBUTE_ID,
    _amounts_for_2024,
    _resolved_population_attribute_id,
)
from maps.models import Attribute, Region, RegionAttributeValue
from utils.properties.models import Property, Unit


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [test]",
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
        cls.population_attribute = Attribute.objects.create(
            name="Population [test]",
            unit="cap",
        )

        cls.collection_system = CollectionSystem.objects.create(
            name="Collection system"
        )
        cls.waste_category = WasteCategory.objects.create(name="Waste category")
        cls.waste_stream = WasteStream.objects.create(
            name="Waste stream",
            category=cls.waste_category,
        )

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
            waste_stream=self.waste_stream,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        if population is not None:
            RegionAttributeValue.objects.create(
                name=f"Population {suffix}",
                region=region,
                attribute=self.population_attribute,
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

        dry_stats = backfill_derived_values(dry_run=True)
        self.assertEqual(dry_stats, {"created": 1, "updated": 1, "skipped": 3})

        write_stats = backfill_derived_values(dry_run=False)
        self.assertEqual(write_stats, {"created": 1, "updated": 1, "skipped": 3})

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
        self.assertEqual(amounts[catchment.pk], round(6.5 * 1000 / 2500, 1))

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
        with override_settings(SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=999999):
            clear_derived_value_config_cache()
            with self.assertRaises(ImproperlyConfigured):
                get_derived_property_config()

    def test_get_derived_property_config_raises_for_ambiguous_names(self):
        Property.objects.create(name="specific waste collected [test]")
        with override_settings(SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None):
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

        with override_settings(SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=999999):
            clear_derived_value_config_cache()
            # Should not raise; handler catches ImproperlyConfigured.
            sync_derived_cpv_on_save(sender=CollectionPropertyValue, instance=cpv)
            sync_derived_cpv_on_delete(sender=CollectionPropertyValue, instance=cpv)

    def test_population_attribute_resolution_uses_fallback_when_misconfigured(self):
        with override_settings(SOILCOM_POPULATION_ATTRIBUTE_ID=999999):
            clear_derived_value_config_cache()
            self.assertEqual(
                _resolved_population_attribute_id(), POPULATION_ATTRIBUTE_ID
            )

    # ------------------------------------------------------------------
    # Happy-path conversion helpers
    # ------------------------------------------------------------------

    def test_convert_specific_to_total_mg_happy_path(self):
        # 50 kg/cap/a × 2000 cap / 1000 = 100.0 Mg/a
        self.assertEqual(convert_specific_to_total_mg(50, 2000), 100.0)
        # 10 kg/cap/a × 500 cap / 1000 = 5.0 Mg/a
        self.assertEqual(convert_specific_to_total_mg(10, 500), 5.0)

    def test_convert_total_to_specific_happy_path(self):
        # 100 Mg/a × 1000 / 2000 cap = 50.0 kg/cap/a
        self.assertEqual(convert_total_to_specific(100, 2000), 50.0)
        # 5 Mg/a × 1000 / 500 cap = 10.0 kg/cap/a
        self.assertEqual(convert_total_to_specific(5, 500), 10.0)

    def test_conversion_helpers_ndigits_none_returns_exact_float(self):
        result = convert_specific_to_total_mg(7, 3000, ndigits=None)
        self.assertEqual(result, 7 * 3000 / 1000)
        result = convert_total_to_specific(7, 3000, ndigits=None)
        self.assertEqual(result, 7 * 1000 / 3000)

    def test_conversion_helpers_respect_ndigits(self):
        # 7 kg/cap/a × 3000 / 1000 = 21.0 (ndigits=1 → 21.0)
        self.assertEqual(convert_specific_to_total_mg(7, 3000, ndigits=1), 21.0)
        # 6.5 Mg/a × 1000 / 2500 = 2.6 (ndigits=1 → 2.6)
        self.assertEqual(convert_total_to_specific(6.5, 2500, ndigits=1), 2.6)

    # ------------------------------------------------------------------
    # compute_counterpart_value: verify returned values
    # ------------------------------------------------------------------

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
        # 80 × 5000 / 1000 = 400.0
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
        # 120 × 1000 / 4000 = 30.0
        self.assertEqual(computed, 30.0)

    # ------------------------------------------------------------------
    # create_or_update: verify DB values (both directions)
    # ------------------------------------------------------------------

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
        # 10 × 2000 / 1000 = 20.0
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
        # 250 × 1000 / 5000 = 50.0
        self.assertEqual(derived.average, 50.0)
        self.assertEqual(derived.property_id, self.property_specific.pk)
        self.assertEqual(derived.unit_id, self.unit_specific.pk)
        self.assertTrue(derived.is_derived)

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
        # 10 × 1000 / 1000 = 10.0
        self.assertEqual(derived1.average, 10.0)

        # Update the source average and re-derive
        cpv.average = 20.0
        cpv.save()
        derived2, action2 = create_or_update_derived_cpv(cpv)
        self.assertEqual(action2, "updated")
        # 20 × 1000 / 1000 = 20.0
        self.assertEqual(derived2.average, 20.0)
        self.assertEqual(derived1.pk, derived2.pk)

    # ------------------------------------------------------------------
    # delete_derived_cpv
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # backfill: verify actual DB values
    # ------------------------------------------------------------------

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
        # 60 × 2000 / 1000 = 120.0
        self.assertEqual(derived_total.average, 120.0)

        derived_specific = CollectionPropertyValue.objects.get(
            collection=collection,
            property=self.property_specific,
            year=2025,
            is_derived=True,
        )
        # 50 × 1000 / 2000 = 25.0
        self.assertEqual(derived_specific.average, 25.0)

    # ------------------------------------------------------------------
    # get_population_for_collection
    # ------------------------------------------------------------------

    def test_get_population_for_collection_returns_exact_year(self):
        collection, _ = self._create_collection("pop-year", population=None)
        region = collection.catchment.region
        RegionAttributeValue.objects.create(
            name="Pop 2023",
            region=region,
            attribute=self.population_attribute,
            date=date(2023, 1, 1),
            value=3000,
        )
        RegionAttributeValue.objects.create(
            name="Pop 2024",
            region=region,
            attribute=self.population_attribute,
            date=date(2024, 6, 15),
            value=3500,
        )
        self.assertEqual(get_population_for_collection(collection, year=2024), 3500)
        self.assertEqual(get_population_for_collection(collection, year=2023), 3000)

    def test_get_population_for_collection_falls_back_to_most_recent(self):
        collection, _ = self._create_collection("pop-fallback", population=None)
        region = collection.catchment.region
        RegionAttributeValue.objects.create(
            name="Pop old",
            region=region,
            attribute=self.population_attribute,
            date=date(2020, 1, 1),
            value=1000,
        )
        RegionAttributeValue.objects.create(
            name="Pop newer",
            region=region,
            attribute=self.population_attribute,
            date=date(2022, 1, 1),
            value=2000,
        )
        # No value for 2024, should fall back to most recent (2022)
        self.assertEqual(get_population_for_collection(collection, year=2024), 2000)

    def test_get_population_for_collection_returns_none_without_data(self):
        collection, _ = self._create_collection("pop-none", population=None)
        self.assertIsNone(get_population_for_collection(collection, year=2024))
