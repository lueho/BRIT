"""Independently asserted numerical contracts for source-bound generation."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.db import router, transaction
from django.test import TestCase

from bibliography.models import Source
from maps.models import Region, RegionAttributeValue, RegionProperty
from maps.population.models import (
    GeographicScope,
    PopulationDataset,
    PopulationObservation,
    TemporalBasis,
)
from sources.waste_collection import derived_values
from sources.waste_collection.derived_values import (
    backfill_derived_values,
    clear_derived_value_config_cache,
    create_or_update_derived_cpv,
)
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.signals import sync_derived_cpv_on_save
from utils.object_management.policy import decide, visible_queryset
from utils.object_management.services import perform_transition
from utils.properties.models import Property, Unit
from utils.tests.testcases import ensure_test_default_owner


class GeneratedPipelineNumericalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls.owner = User.objects.create_user("numeric-source-owner")
        cls.stranger = User.objects.create_user("numeric-source-stranger")
        public = {"owner": cls.owner, "publication_status": "published"}
        cls.specific = Property.objects.create(name="numeric specific", **public)
        cls.total = Property.objects.create(name="numeric total", **public)
        cls.specific_unit = Unit.objects.create(name="numeric kg/cap/a", **public)
        cls.total_unit = Unit.objects.create(name="numeric Mg/a", **public)
        cls.population = RegionProperty.objects.create(
            name="numeric population", **public
        )
        cls.region = Region.objects.create(
            name="Numeric region", country="DE", **public
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Numeric catchment",
            region=cls.region,
            owner=cls.owner,
            publication_status="published",
        )
        cls.collection = Collection.objects.create(
            owner=cls.owner,
            publication_status="published",
            catchment=cls.catchment,
            collection_system=CollectionSystem.objects.create(
                name="Numeric system", **public
            ),
            waste_category=WasteCategory.objects.create(
                name="Numeric category", **public
            ),
            valid_from=date(2024, 1, 1),
        )
        cls.average_dataset = PopulationDataset.objects.create(
            slug="numeric-annual-average",
            name="Synthetic annual-average population",
            provider="Synthetic test fixture",
            source_code="fixture-annual-average",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.CALENDAR_YEAR_AVERAGE,
            source_unit="NR",
            classification_version="fixture-v1",
            is_canonical=True,
        )
        cls.population_observation = PopulationObservation.objects.create(
            dataset=cls.average_dataset,
            region=cls.region,
            year=2024,
            value=Decimal("2000"),
        )
        PopulationObservation.objects.create(
            dataset=cls.average_dataset,
            region=cls.region,
            year=2025,
            value=Decimal("9000"),
        )
        cls.stock_dataset = PopulationDataset.objects.create(
            slug="a-numeric-point-in-time",
            name="Synthetic point-in-time stock",
            provider="Synthetic test fixture",
            source_code="fixture-stock",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.POINT_IN_TIME,
            source_unit="NR",
            classification_version="fixture-v1",
            is_canonical=True,
        )
        for year, value in ((2023, "8888"), (2024, "9999")):
            PopulationObservation.objects.create(
                dataset=cls.stock_dataset,
                region=cls.region,
                year=year,
                value=Decimal(value),
            )

    def setUp(self):
        self.config = self.settings(
            WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID=self.specific.pk,
            WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID=self.total.pk,
            WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID=self.specific_unit.pk,
            WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID=self.total_unit.pk,
            WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID=self.population.pk,
        )
        self.config.enable()
        clear_derived_value_config_cache()
        self.addCleanup(self.config.disable)
        self.addCleanup(clear_derived_value_config_cache)

    def _raw(self, prop, unit, average, *, owner=None, state="private", year=2024):
        row = CollectionPropertyValue(
            collection=self.collection,
            property=prop,
            unit=unit,
            average=Decimal(average),
            year=year,
            owner=owner or self.owner,
            publication_status=state,
            is_derived=False,
        )
        CollectionPropertyValue.objects.bulk_create([row])
        return row

    def _assert_output(self, source, prop, unit, average):
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
        raw_before = CollectionPropertyValue.objects.values(*raw_fields).get(
            pk=source.pk
        )
        generated, action = create_or_update_derived_cpv(source)
        self.assertIn(action, {"created", "updated"})
        self.assertEqual(
            CollectionPropertyValue.objects.values(*raw_fields).get(pk=source.pk),
            raw_before,
        )
        generated.refresh_from_db()
        self.assertEqual(getattr(generated, "derived_from_id", None), source.pk)
        self.assertTrue(generated.is_derived)
        self.assertEqual(generated.collection_id, self.collection.pk)
        self.assertEqual(generated.year, 2024)
        self.assertEqual(generated.property_id, prop.pk)
        self.assertEqual(generated.unit_id, unit.pk)
        self.assertEqual(Decimal(str(generated.average)), Decimal(average))
        self.assertIsNone(generated.standard_deviation)
        self.assertEqual(generated.owner_id, source.owner_id)
        self.assertEqual(generated.publication_status, source.publication_status)
        for field in ("submitted_at", "approved_at", "approved_by_id"):
            self.assertEqual(getattr(generated, field), getattr(source, field))
        description = json.loads(generated.description)
        self.assertEqual(description["source_cpv"]["id"], source.pk)
        self.assertEqual(description["source_cpv"]["unit_id"], source.unit_id)
        self.assertEqual(
            Decimal(description["source_cpv"]["average"]),
            Decimal(str(raw_before["average"])),
        )
        self.assertEqual(Decimal(description["population"]["value"]), Decimal("2000"))
        self.assertEqual(description["population"]["year"], 2024)
        self.assertEqual(
            description["population"]["temporal_basis"],
            TemporalBasis.CALENDAR_YEAR_AVERAGE,
        )
        self.assertEqual(description["population"]["method"], "direct")
        self.assertFalse(description["population"]["is_provisional"])
        self.assertFalse(description["population"]["is_mixed_provenance"])
        observations = description["population"]["observations"]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["id"], self.population_observation.pk)
        self.assertEqual(observations[0]["dataset"], self.average_dataset.slug)
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
            (
                self.specific,
                self.specific_unit,
                "175",
                self.total,
                self.total_unit,
                "350",
            ),
        ]
        for prop, unit, amount, target_prop, target_unit, expected in cases:
            with self.subTest(property=prop.name, amount=amount):
                source = self._raw(prop, unit, amount)
                self._assert_output(source, target_prop, target_unit, expected)

    def test_stale_source_instance_cannot_overwrite_fresh_output(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        first = self._assert_output(source, self.total, self.total_unit, "300")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(average=175)
        second = self._assert_output(source, self.total, self.total_unit, "350")
        self.assertEqual(second.pk, first.pk)

    def test_manual_and_independent_sources_keep_distinct_outputs(self):
        one = self._raw(self.specific, self.specific_unit, "150")
        two = self._raw(self.specific, self.specific_unit, "175")
        manual = self._raw(self.total, self.total_unit, "400")
        first = self._assert_output(one, self.total, self.total_unit, "300")
        second = self._assert_output(two, self.total, self.total_unit, "350")
        self.assertNotEqual(first.pk, second.pk)
        manual.refresh_from_db()
        self.assertFalse(manual.is_derived)
        self.assertIsNone(manual.derived_from_id)
        self.assertEqual(manual.average, Decimal("400"))
        one.delete()
        self.assertFalse(CollectionPropertyValue.objects.filter(pk=first.pk).exists())
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=second.pk).exists())
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=manual.pk).exists())

    def test_stock_legacy_and_other_year_population_do_not_substitute(self):
        RegionAttributeValue.objects.create(
            name="Synthetic legacy population 2023",
            region=self.region,
            property=self.population,
            date=date(2023, 1, 1),
            value=7700,
            owner=self.owner,
            publication_status="published",
        )
        source = self._raw(self.specific, self.specific_unit, "150", year=2023)
        output, action = create_or_update_derived_cpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")
        self.assertFalse(source.generated_values.exists())

    def test_wrong_unit_invalidates_only_own_linked_output(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        other = self._raw(self.specific, self.specific_unit, "175")
        first = self._assert_output(source, self.total, self.total_unit, "300")
        second = self._assert_output(other, self.total, self.total_unit, "350")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            unit=self.total_unit
        )
        output, action = create_or_update_derived_cpv(source)
        self.assertIsNone(output)
        self.assertEqual(action, "skipped")
        self.assertFalse(CollectionPropertyValue.objects.filter(pk=first.pk).exists())
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=second.pk).exists())

    def test_private_manual_does_not_suppress_public_projection(self):
        source = self._raw(self.specific, self.specific_unit, "150", state="published")
        generated = self._assert_output(source, self.total, self.total_unit, "300")
        hidden = self._raw(
            self.total, self.total_unit, "400", owner=self.stranger, state="private"
        )
        authorized = visible_queryset(
            AnonymousUser(), CollectionPropertyValue.objects.all()
        )
        preferred = derived_values.preferred_measurement_queryset(authorized)
        self.assertTrue(preferred.filter(pk=generated.pk).exists())
        self.assertFalse(preferred.filter(pk=hidden.pk).exists())
        public_manual = self._raw(self.total, self.total_unit, "450", state="published")
        preferred = derived_values.preferred_measurement_queryset(
            visible_queryset(AnonymousUser(), CollectionPropertyValue.objects.all())
        )
        self.assertFalse(preferred.filter(pk=generated.pk).exists())
        self.assertTrue(preferred.filter(pk=public_manual.pk).exists())

    def test_dry_run_and_real_backfill_agree_without_unit_guessing(self):
        valid = self._raw(self.specific, self.specific_unit, "150")
        invalid = self._raw(self.specific, self.total_unit, "150")
        before = set(CollectionPropertyValue.objects.values_list("pk", flat=True))
        expected = {"created": 1, "updated": 0, "skipped": 1}
        self.assertEqual(backfill_derived_values(dry_run=True), expected)
        self.assertEqual(
            set(CollectionPropertyValue.objects.values_list("pk", flat=True)), before
        )
        self.assertEqual(backfill_derived_values(), expected)
        self._assert_output(valid, self.total, self.total_unit, "300")
        self.assertFalse(invalid.generated_values.exists())

    def test_signal_failure_rolls_back_source_and_output_atomically(self):
        source = self._raw(self.specific, self.specific_unit, "150", state="private")
        generated = self._assert_output(source, self.total, self.total_unit, "300")
        seen = []

        def fail_after_source_save(locked_source):
            seen.append(
                (
                    locked_source.average,
                    CollectionPropertyValue.objects.filter(pk=generated.pk).exists(),
                )
            )
            raise RuntimeError("injected numerical sync failure")

        with (
            self.assertLogs(
                "sources.waste_collection.signals", level="ERROR"
            ) as logged,
            self.assertRaisesRegex(RuntimeError, "injected numerical sync failure"),
            transaction.atomic(),
            patch(
                "sources.waste_collection.derived_values._compute_counterpart_value",
                side_effect=fail_after_source_save,
            ),
        ):
            source.average = 175
            source.save(update_fields=["average"])
        source.refresh_from_db()
        generated.refresh_from_db()
        self.assertEqual(seen, [(175, True)])
        self.assertEqual(source.average, Decimal("150"))
        self.assertEqual(generated.average, Decimal("300"))
        self.assertIn("Failed to sync derived CPV", "\n".join(logged.output))

    def test_compatibility_metadata_neither_fabricates_review_nor_grants_read(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated, action = create_or_update_derived_cpv(
            source,
            owner=self.stranger,
            publication_status="published",
        )
        self.assertEqual(action, "created")
        generated.refresh_from_db()
        self.assertEqual(generated.owner_id, self.stranger.pk)
        self.assertEqual(generated.publication_status, "published")
        self.assertIsNone(generated.approved_at)
        self.assertIsNone(generated.approved_by_id)
        queryset = CollectionPropertyValue.objects.filter(pk=generated.pk)
        self.assertFalse(visible_queryset(AnonymousUser(), queryset).exists())
        self.assertFalse(visible_queryset(self.stranger, queryset).exists())
        self.assertTrue(visible_queryset(self.owner, queryset).exists())
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "private")
        self.assertIsNone(source.approved_at)
        self.assertIsNone(source.approved_by_id)

    def test_direct_failure_invalidates_only_the_failed_sources_output(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        other = self._raw(self.specific, self.specific_unit, "175")
        first = self._assert_output(source, self.total, self.total_unit, "300")
        second = self._assert_output(other, self.total, self.total_unit, "350")
        manual = self._raw(self.total, self.total_unit, "400")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(average=175)
        with (
            patch.object(
                derived_values,
                "_compute_counterpart_value",
                side_effect=RuntimeError("synthetic numerical failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "synthetic numerical failure"),
        ):
            create_or_update_derived_cpv(source)
        source.refresh_from_db()
        second.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(source.average, 175)
        self.assertFalse(CollectionPropertyValue.objects.filter(pk=first.pk).exists())
        self.assertEqual(second.average, 350)
        self.assertEqual(manual.average, 400)
        self.assertFalse(manual.is_derived)

    def test_partial_output_write_is_rolled_back_before_invalidation(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        original = self._assert_output(source, self.total, self.total_unit, "300")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(average=175)
        write = derived_values._write_locked_projection
        seen = []

        def fail_after_write(locked_source, **kwargs):
            output, _action = write(locked_source, **kwargs)
            seen.append((output.pk, output.average))
            raise RuntimeError("synthetic post-write failure")

        with (
            patch.object(derived_values, "_write_locked_projection", fail_after_write),
            self.assertRaisesRegex(RuntimeError, "synthetic post-write failure"),
        ):
            create_or_update_derived_cpv(source)
        self.assertEqual(seen, [(original.pk, 350)])
        self.assertFalse(source.generated_values.exists())
        source.refresh_from_db()
        self.assertEqual(source.average, 175)

    def test_signal_does_not_delete_a_newer_output_after_generator_failure(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        original = self._assert_output(source, self.total, self.total_unit, "300")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(average=175)
        generator = create_or_update_derived_cpv
        replacements = []

        def fail_then_regenerate(instance):
            failure = None
            with patch.object(
                derived_values,
                "_compute_counterpart_value",
                side_effect=RuntimeError("synthetic intervening failure"),
            ):
                try:
                    generator(instance)
                except RuntimeError as exc:
                    failure = exc
            self.assertIsNotNone(failure)
            replacement, action = generator(instance)
            self.assertEqual(action, "created")
            replacements.append(replacement.pk)
            raise failure

        with (
            patch(
                "sources.waste_collection.signals.create_or_update_derived_cpv",
                side_effect=fail_then_regenerate,
            ),
            self.assertLogs(
                "sources.waste_collection.signals", level="ERROR"
            ) as logged,
            self.assertRaisesRegex(RuntimeError, "synthetic intervening failure"),
        ):
            sync_derived_cpv_on_save(CollectionPropertyValue, source)
        self.assertIn("Failed to sync derived CPV", "\n".join(logged.output))
        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=original.pk).exists()
        )
        replacement = source.generated_values.get()
        self.assertEqual(replacements, [replacement.pk])
        self.assertEqual(replacement.average, 350)

    def test_dry_run_failure_is_read_only_but_real_backfill_invalidates(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        self._assert_output(source, self.total, self.total_unit, "300")
        CollectionPropertyValue.objects.filter(pk=source.pk).update(average=175)
        before = list(CollectionPropertyValue.objects.order_by("pk").values())
        with patch.object(
            derived_values,
            "_compute_counterpart_value",
            side_effect=RuntimeError("synthetic backfill failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic backfill failure"):
                backfill_derived_values(dry_run=True)
            self.assertEqual(
                list(CollectionPropertyValue.objects.order_by("pk").values()),
                before,
            )
            with self.assertRaisesRegex(RuntimeError, "synthetic backfill failure"):
                backfill_derived_values()
        self.assertFalse(source.generated_values.exists())
        source.refresh_from_db()
        self.assertEqual(source.average, 175)

    def test_backfill_invalidates_a_linked_source_changed_to_another_property(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._assert_output(source, self.total, self.total_unit, "300")
        other_property = Property.objects.create(
            name="Synthetic unrelated measurement",
            owner=self.owner,
            publication_status="published",
        )
        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            property=other_property
        )
        expected = {"created": 0, "updated": 0, "skipped": 1}
        self.assertEqual(backfill_derived_values(dry_run=True), expected)
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )
        self.assertEqual(backfill_derived_values(), expected)
        self.assertFalse(source.generated_values.exists())
        source.refresh_from_db()
        self.assertEqual(source.property_id, other_property.pk)
        self.assertEqual(source.average, 150)

    # -- Source-save preservation: metadata-only saves must not delete a
    # linked output when the input cannot currently be recomputed ----------

    def _linked_output(self, source, average="300"):
        source = CollectionPropertyValue.objects.get(pk=source.pk)
        generated, action = create_or_update_derived_cpv(source)
        self.assertIn(action, {"created", "updated"})
        self.assertEqual(Decimal(str(generated.average)), Decimal(average))
        return generated

    def test_metadata_save_preserves_link_without_population(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        description_before = generated.description
        revision_before = generated.content_revision
        self.population_observation.delete()

        source.refresh_from_db()
        source.description = "metadata only"
        source.save(update_fields=["description"])

        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )
        generated.refresh_from_db()
        self.assertEqual(generated.derived_from_id, source.pk)
        self.assertEqual(generated.average, Decimal("300"))
        self.assertEqual(generated.description, description_before)
        self.assertEqual(generated.content_revision, revision_before)

    def test_full_save_and_noop_update_fields_preserve_link(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        self.population_observation.delete()

        source.refresh_from_db()
        source.description = "full save metadata"
        source.save()
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )

        # Unchanged full save: every field identical, no recompute.
        source.refresh_from_db()
        source.save()
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )

        source.refresh_from_db()
        source.save(update_fields=["average"])
        generated.refresh_from_db()
        self.assertEqual(generated.average, Decimal("300"))
        self.assertEqual(generated.derived_from_id, source.pk)

    def test_stale_inmemory_average_partial_save_preserves_link(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        self.population_observation.delete()

        source.average = Decimal("999")  # stale in-memory, never persisted
        source.description = "stale average excluded"
        source.save(update_fields=["description"])

        source.refresh_from_db()
        self.assertEqual(source.average, Decimal("150"))
        generated.refresh_from_db()
        self.assertEqual(generated.average, Decimal("300"))
        self.assertEqual(generated.derived_from_id, source.pk)

    def test_status_change_refreshes_copied_metadata_without_recompute(self):
        source = self._raw(self.specific, self.specific_unit, "150", state="private")
        generated = self._linked_output(source)
        self.population_observation.delete()
        qs = CollectionPropertyValue.objects.filter(pk=generated.pk)

        # Private source -> anonymous cannot see the projection either.
        self.assertFalse(visible_queryset(AnonymousUser(), qs).exists())
        self.assertFalse(decide(AnonymousUser(), "export", generated).allowed)

        source.refresh_from_db()
        source.publication_status = "published"
        source.save(update_fields=["publication_status"])

        generated.refresh_from_db()
        self.assertEqual(generated.average, Decimal("300"))
        self.assertEqual(generated.publication_status, "published")
        self.assertTrue(visible_queryset(AnonymousUser(), qs).exists())
        self.assertTrue(decide(AnonymousUser(), "read", generated).allowed)
        self.assertTrue(decide(AnonymousUser(), "export", generated).allowed)
        # Copied metadata is still not a governance surface: the projection
        # itself remains read-only for the source owner.
        self.assertFalse(decide(self.owner, "edit", generated).allowed)

        source.refresh_from_db()
        source.publication_status = "declined"
        source.save(update_fields=["publication_status"])
        generated.refresh_from_db()
        self.assertEqual(generated.publication_status, "declined")
        self.assertIsNone(generated.approved_at)
        self.assertIsNone(generated.approved_by_id)
        self.assertIsNone(generated.submitted_at)
        self.assertEqual(generated.average, Decimal("300"))
        self.assertFalse(visible_queryset(AnonymousUser(), qs).exists())
        self.assertFalse(decide(AnonymousUser(), "read", generated).allowed)
        self.assertFalse(decide(AnonymousUser(), "export", generated).allowed)

    def test_governed_transition_refreshes_metadata_without_recompute(self):
        source = self._raw(self.specific, self.specific_unit, "150", state="private")
        generated = self._linked_output(source)
        self.population_observation.delete()
        perform_transition(
            self.owner,
            source,
            "submit",
            expected_revision=source.content_revision,
        )

        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        generated.refresh_from_db()
        self.assertEqual(generated.publication_status, "review")
        self.assertEqual(generated.average, Decimal("300"))
        self.assertFalse(decide(AnonymousUser(), "read", generated).allowed)
        self.assertFalse(decide(AnonymousUser(), "export", generated).allowed)

    def test_owner_and_source_links_preserved_on_metadata_save(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        ref = Source.objects.create(
            abbreviation="SYNTH-24",
            title="Synthetic reference",
            type="officialStatistics",
            publication_status="published",
            owner=self.owner,
        )
        generated.sources.add(ref)
        before = CollectionPropertyValue.objects.values(
            "average",
            "description",
            "content_revision",
            "created_at",
            "lastmodified_at",
        ).get(pk=generated.pk)
        self.population_observation.delete()

        source.refresh_from_db()
        source.owner = self.stranger
        source.save(update_fields=["owner"])

        generated.refresh_from_db()
        self.assertEqual(generated.owner_id, self.stranger.pk)
        self.assertFalse(decide(self.owner, "read", generated).allowed)
        self.assertTrue(decide(self.stranger, "read", generated).allowed)
        self.assertFalse(decide(self.stranger, "edit", generated).allowed)
        after = CollectionPropertyValue.objects.values(
            "average",
            "description",
            "content_revision",
            "created_at",
            "lastmodified_at",
        ).get(pk=generated.pk)
        self.assertEqual(after, before)
        self.assertEqual(list(generated.sources.values_list("pk", flat=True)), [ref.pk])

    def test_input_change_to_year_or_unit_also_invalidates(self):
        for field, value in (("year", 2023), ("unit_id", self.total_unit.pk)):
            with self.subTest(field=field):
                if not PopulationObservation.objects.filter(
                    pk=self.population_observation.pk
                ).exists():
                    self.population_observation.pk = None
                    self.population_observation.save(force_insert=True)
                source = self._raw(self.specific, self.specific_unit, "150")
                generated = self._linked_output(source)
                self.population_observation.delete()
                source.refresh_from_db()
                setattr(source, field, value)
                source.save(update_fields=[field])
                self.assertFalse(
                    CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
                )

    def test_real_input_change_invalidates_only_its_output(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        other = self._raw(self.specific, self.specific_unit, "100")
        other_output = self._linked_output(other, "200")
        self.population_observation.delete()

        source.refresh_from_db()
        source.average = Decimal("175")
        source.save(update_fields=["average"])

        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=other_output.pk).exists()
        )

    def test_input_change_recomputes_with_population(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)

        source.refresh_from_db()
        source.average = Decimal("175")
        source.save(update_fields=["average"])

        generated.refresh_from_db()
        self.assertEqual(generated.average, Decimal("350"))
        self.assertEqual(generated.derived_from_id, source.pk)

    def test_direct_generator_still_invalidates_without_population(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        self.population_observation.delete()

        source.refresh_from_db()
        generated_result, action = create_or_update_derived_cpv(source)

        self.assertEqual((generated_result, action), (None, "skipped"))
        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=generated.pk).exists()
        )

    def test_signal_failure_rolls_back_source_and_output(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        generated = self._linked_output(source)
        source.refresh_from_db()
        before = (source.average, generated.average)

        with (
            patch(
                "sources.waste_collection.derived_values._write_locked_projection",
                side_effect=RuntimeError("synthetic signal failure"),
            ),
            self.assertLogs("sources.waste_collection.signals", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            source.average = Decimal("175")
            source.save(update_fields=["average"])

        self.assertTrue(
            any("Failed to sync derived CPV" in line for line in logs.output)
        )
        source.refresh_from_db()
        self.assertEqual(source.average, before[0])
        generated.refresh_from_db()
        self.assertEqual(generated.average, before[1])
        self.assertEqual(generated.derived_from_id, source.pk)

    def test_new_raw_signal_failure_leaves_nothing_committed(self):
        """A failed save on an unsaved raw row commits no row and no output."""
        count_before = CollectionPropertyValue.objects.count()
        source = CollectionPropertyValue(
            collection=self.collection,
            property=self.specific,
            unit=self.specific_unit,
            average=Decimal("175"),
            year=2024,
            owner=self.owner,
            publication_status="private",
            is_derived=False,
        )
        with (
            patch(
                "sources.waste_collection.derived_values._write_locked_projection",
                side_effect=RuntimeError("synthetic signal failure"),
            ),
            self.assertLogs("sources.waste_collection.signals", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            source.save()
        self.assertTrue(
            any("Failed to sync derived CPV" in line for line in logs.output)
        )
        self.assertEqual(CollectionPropertyValue.objects.count(), count_before)
        self.assertFalse(CollectionPropertyValue.objects.filter(pk=source.pk).exists())
        self.assertFalse(
            CollectionPropertyValue.objects.filter(is_derived=True).exists()
        )

    def test_save_resolves_write_alias_from_the_loaded_instance(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        seen = []
        real = router.db_for_write

        def wrapped(model, **hints):
            seen.append(hints.get("instance"))
            return real(model, **hints)

        with patch("django.db.router.db_for_write", side_effect=wrapped):
            source.description = "alias check"
            source.save(update_fields=["description"])
        self.assertIn(source, seen)
