"""
Tests for Collection-related signal behavior.

These tests verify that:
1. Signal handlers fire correctly on full saves
2. Signal handlers respect update_fields to skip unnecessary work
3. Cache invalidation, orphan cleanup, and name updates work as expected
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from materials.models import MaterialCategory

from ..forms import CollectionModelForm
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteComponent,
    WasteStream,
)
from ..tasks import cleanup_orphaned_waste_streams


def dict_to_querydict(data):
    """Convert a dict to QueryDict for form testing."""
    from django.http import QueryDict

    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, list):
            qd.setlist(key, value)
        else:
            qd[key] = value
    return qd


class DeleteUnusedWasteStreamsSignalTestCase(TestCase):
    """Tests for the delete_unused_waste_streams signal handler."""

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.waste_stream = WasteStream.objects.create(
            name="Used Stream", category=cls.category
        )
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_stream=cls.waste_stream,
            valid_from=date(2024, 1, 1),
        )

    def test_orphan_waste_streams_are_deleted_on_waste_stream_change(self):
        """Verify unused WasteStreams are cleaned up when waste_stream changes."""
        orphan_stream = WasteStream.objects.create(
            name="Orphan Stream", category=self.category
        )
        new_stream = WasteStream.objects.create(
            name="New Stream", category=self.category
        )

        with patch(
            "case_studies.soilcom.models.celery.current_app.send_task"
        ) as mock_send_task:
            self.collection.waste_stream = new_stream
            self.collection.save(update_fields=["waste_stream"])

        mock_send_task.assert_called_once_with("cleanup_orphaned_waste_streams")
        cleanup_orphaned_waste_streams()

        self.assertFalse(WasteStream.objects.filter(pk=orphan_stream.pk).exists())
        self.assertFalse(WasteStream.objects.filter(pk=self.waste_stream.pk).exists())
        self.assertTrue(WasteStream.objects.filter(pk=new_stream.pk).exists())

    def test_orphan_cleanup_not_scheduled_when_waste_stream_unchanged(self):
        """Verify cleanup is not scheduled when waste_stream is unchanged."""
        orphan_stream = WasteStream.objects.create(
            name="Orphan Stream 2", category=self.category
        )
        self.assertTrue(WasteStream.objects.filter(pk=orphan_stream.pk).exists())

        with patch(
            "case_studies.soilcom.models.celery.current_app.send_task"
        ) as mock_send_task:
            self.collection.description = "Updated"
            self.collection.save()

        mock_send_task.assert_not_called()
        self.assertTrue(WasteStream.objects.filter(pk=orphan_stream.pk).exists())

    def test_orphan_cleanup_not_scheduled_with_update_fields(self):
        """Verify cleanup is not scheduled when update_fields excludes waste_stream."""
        orphan_stream = WasteStream.objects.create(
            name="Orphan Stream 3", category=self.category
        )
        self.assertTrue(WasteStream.objects.filter(pk=orphan_stream.pk).exists())

        with patch(
            "case_studies.soilcom.models.celery.current_app.send_task"
        ) as mock_send_task:
            self.collection.valid_until = date(2024, 12, 31)
            self.collection.save(update_fields=["valid_until"])

        mock_send_task.assert_not_called()
        self.assertTrue(WasteStream.objects.filter(pk=orphan_stream.pk).exists())


class InvalidateCollectionCacheSignalTestCase(TestCase):
    """Tests for the invalidate_collection_geojson_cache signal handler."""

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.waste_stream = WasteStream.objects.create(
            name="Stream", category=cls.category
        )
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_stream=cls.waste_stream,
            valid_from=date(2024, 1, 1),
        )

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_cache_cleared_on_full_collection_save(self, mock_clear):
        """Verify cache is invalidated on full save."""
        self.collection.description = "Updated description"
        self.collection.save()

        mock_clear.assert_called_once_with("collection_geojson:*")

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_cache_cleared_on_save_with_geojson_affecting_field(self, mock_clear):
        """Verify cache is invalidated when GeoJSON-affecting fields change."""
        self.collection.description = "Updated description"
        self.collection.save(update_fields=["description"])

        # Cache should be cleared for fields that affect GeoJSON
        mock_clear.assert_called_once_with("collection_geojson:*")

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_cache_not_cleared_on_valid_until_update(self, mock_clear):
        """Verify cache is NOT cleared for valid_until updates.

        valid_until is a non-GeoJSON field used for predecessor updates.
        """
        self.collection.valid_until = date(2024, 12, 31)
        self.collection.save(update_fields=["valid_until"])

        # Cache should NOT be cleared for valid_until-only updates
        mock_clear.assert_not_called()

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_cache_not_cleared_on_name_only_update(self, mock_clear):
        """Verify cache is NOT cleared for name-only updates.

        Name changes don't affect GeoJSON representation, so cache
        invalidation is skipped for performance optimization.
        """
        self.collection.name = "New Name"
        self.collection.save(update_fields=["name"])

        # Cache should NOT be cleared for name-only updates
        mock_clear.assert_not_called()


class UpdateCollectionNamesSignalTestCase(TestCase):
    """Tests for the update_collection_names signal handler."""

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.waste_stream = WasteStream.objects.create(
            name="Stream", category=cls.category
        )
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_stream=cls.waste_stream,
            valid_from=date(2024, 1, 1),
        )

    def test_collection_name_updated_when_system_changes(self):
        """Verify Collection name is updated when CollectionSystem name changes."""
        original_name = self.collection.name
        self.system.name = "New System"
        self.system.save()

        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.name, original_name)
        self.assertIn("New System", self.collection.name)

    def test_collection_name_updated_when_catchment_changes(self):
        """Verify Collection name is updated when Catchment name changes."""
        original_name = self.collection.name
        self.catchment.name = "New Catchment"
        self.catchment.save()

        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.name, original_name)
        self.assertIn("New Catchment", self.collection.name)

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_name_update_does_not_trigger_cache_invalidation(self, mock_clear):
        """Verify name updates via update_collection_names don't trigger cache clear.

        When a CollectionSystem name changes, all related Collection names are
        updated using update_fields=['name', 'lastmodified_at'], which skips
        cache invalidation since names don't affect GeoJSON.
        """
        # Create additional collections using this system
        Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_stream=self.waste_stream,
            valid_from=date(2023, 1, 1),
        )
        Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_stream=self.waste_stream,
            valid_from=date(2022, 1, 1),
        )

        mock_clear.reset_mock()

        # Update system name - triggers update_collection_names signal
        self.system.name = "Updated System"
        self.system.save()

        # Cache invalidation should be skipped for name-only updates
        self.assertEqual(mock_clear.call_count, 0)


class CollectionFormPredecessorSaveTestCase(TestCase):
    """Tests for predecessor handling in CollectionModelForm.save()."""

    @classmethod
    def setUpTestData(cls):
        MaterialCategory.objects.get_or_create(
            name="Biowaste component", publication_status="published"
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.allowed_material = WasteComponent.objects.create(
            name="Allowed", publication_status="published"
        )
        biowaste_cat = MaterialCategory.objects.get(name="Biowaste component")
        cls.allowed_material.categories.add(biowaste_cat)
        cls.waste_stream = WasteStream.objects.create(
            name="Stream", category=cls.category
        )
        cls.waste_stream.allowed_materials.add(cls.allowed_material)
        cls.frequency = CollectionFrequency.objects.create(
            name="Frequency", publication_status="published"
        )
        cls.predecessor = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_stream=cls.waste_stream,
            valid_from=date(2023, 1, 1),
            publication_status="published",
        )
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_stream=cls.waste_stream,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        cls.collection.predecessors.add(cls.predecessor)

    def test_predecessor_valid_until_updated_on_form_save(self):
        """Verify predecessors' valid_until is updated when form is saved."""
        self.assertIsNone(self.predecessor.valid_until)

        form_data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.system.id,
            "waste_category": self.category.id,
            "allowed_materials": [self.allowed_material.id],
            "forbidden_materials": [],
            "frequency": self.frequency.id,
            "valid_from": date(2024, 6, 1),
            "connection_type": "VOLUNTARY",
        }
        form = CollectionModelForm(
            instance=self.collection, data=dict_to_querydict(form_data)
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.predecessor.refresh_from_db()
        self.assertEqual(self.predecessor.valid_until, date(2024, 5, 31))

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_predecessor_save_minimizes_cache_invalidation(self, mock_clear):
        """Verify predecessor updates minimize cache invalidation calls.

        Predecessor valid_until updates use save(update_fields=...),
        which skips cache invalidation. Only the main collection save
        and the form's final save trigger cache invalidation.
        """
        # Add another predecessor
        predecessor2 = Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_stream=self.waste_stream,
            valid_from=date(2022, 1, 1),
            publication_status="published",
        )
        self.collection.predecessors.add(predecessor2)

        mock_clear.reset_mock()

        form_data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.system.id,
            "waste_category": self.category.id,
            "allowed_materials": [self.allowed_material.id],
            "forbidden_materials": [],
            "frequency": self.frequency.id,
            "valid_from": date(2024, 6, 1),
            "connection_type": "VOLUNTARY",
        }
        form = CollectionModelForm(
            instance=self.collection, data=dict_to_querydict(form_data)
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        # With 2 predecessors, old behavior would be 4+ cache clears.
        # New behavior: predecessor saves skip cache, only one main save triggers it.
        self.assertLessEqual(mock_clear.call_count, 1)


class WasteStreamSaveOptimizationTestCase(TestCase):
    """Tests for WasteStream save optimization in CollectionModelForm."""

    @classmethod
    def setUpTestData(cls):
        MaterialCategory.objects.get_or_create(
            name="Biowaste component", publication_status="published"
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.allowed_material = WasteComponent.objects.create(
            name="Allowed", publication_status="published"
        )
        biowaste_cat = MaterialCategory.objects.get(name="Biowaste component")
        cls.allowed_material.categories.add(biowaste_cat)
        cls.frequency = CollectionFrequency.objects.create(
            name="Frequency", publication_status="published"
        )

    def test_new_waste_stream_created_when_needed(self):
        """Verify a new WasteStream is created when no matching one exists."""
        initial_count = WasteStream.objects.count()

        form_data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.system.id,
            "waste_category": self.category.id,
            "allowed_materials": [self.allowed_material.id],
            "forbidden_materials": [],
            "frequency": self.frequency.id,
            "valid_from": date(2024, 1, 1),
            "connection_type": "VOLUNTARY",
        }
        form = CollectionModelForm(data=dict_to_querydict(form_data))
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner_id = 1
        instance = form.save()

        self.assertEqual(WasteStream.objects.count(), initial_count + 1)
        self.assertIsNotNone(instance.waste_stream)

    def test_existing_waste_stream_reused(self):
        """Verify existing WasteStream is reused when a matching one exists."""
        # Create a WasteStream that matches
        existing_stream = WasteStream.objects.create(
            name="Existing", category=self.category
        )
        existing_stream.allowed_materials.add(self.allowed_material)

        initial_count = WasteStream.objects.count()

        form_data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.system.id,
            "waste_category": self.category.id,
            "allowed_materials": [self.allowed_material.id],
            "forbidden_materials": [],
            "frequency": self.frequency.id,
            "valid_from": date(2024, 1, 1),
            "connection_type": "VOLUNTARY",
        }
        form = CollectionModelForm(data=dict_to_querydict(form_data))
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner_id = 1
        instance = form.save()

        # No new WasteStream should be created
        self.assertEqual(WasteStream.objects.count(), initial_count)
        self.assertEqual(instance.waste_stream.pk, existing_stream.pk)

    @patch("case_studies.soilcom.signals.clear_geojson_cache_pattern")
    def test_reusing_waste_stream_minimizes_cache_clears(self, mock_clear):
        """Verify reusing WasteStream minimizes cache invalidation.

        When reusing an existing WasteStream, no WasteStream.save() is called,
        so update_collection_names doesn't fire for related collections.
        Cache clears come only from the new Collection's saves.
        """
        # Create a WasteStream that matches
        existing_stream = WasteStream.objects.create(
            name="Existing2", category=self.category
        )
        existing_stream.allowed_materials.add(self.allowed_material)

        # Create a collection using this stream
        Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_stream=existing_stream,
            valid_from=date(2023, 1, 1),
        )

        mock_clear.reset_mock()

        form_data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.system.id,
            "waste_category": self.category.id,
            "allowed_materials": [self.allowed_material.id],
            "forbidden_materials": [],
            "frequency": self.frequency.id,
            "valid_from": date(2024, 1, 1),
            "connection_type": "VOLUNTARY",
        }
        form = CollectionModelForm(data=dict_to_querydict(form_data))
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner_id = 1
        form.save()

        # With old behavior, WasteStream.save() would trigger cache clears
        # for all related collections. New behavior minimizes this.
        # Expect <= 2 calls (form save calls instance.save() and super().save())
        self.assertLessEqual(mock_clear.call_count, 2)
