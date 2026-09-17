"""Tests for sources.waste_collection.signals."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from ..models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    Collector,
    WasteCategory,
)


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
        cls.private_collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status="private",
        )
        cls.published_collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 2, 1),
            publication_status="published",
        )

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    @patch("sources.waste_collection.signals._schedule_cache_warmup")
    def test_cache_not_cleared_on_private_full_collection_save(
        self, mock_warmup, mock_clear
    ):
        """Private-only saves should not invalidate published GeoJSON cache."""
        self.private_collection.description = "Updated description"
        self.private_collection.save()

        mock_clear.assert_not_called()
        mock_warmup.assert_not_called()

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    @patch("sources.waste_collection.signals._schedule_cache_warmup")
    def test_cache_cleared_on_published_full_collection_save(
        self, mock_warmup, mock_clear
    ):
        """Published saves must invalidate and warm the collection GeoJSON cache."""
        self.published_collection.description = "Updated description"
        self.published_collection.save()

        mock_clear.assert_called_once_with("collection_geojson:*")
        mock_warmup.assert_called_once()

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    @patch("sources.waste_collection.signals._schedule_cache_warmup")
    def test_cache_cleared_when_status_changes_from_published_to_private(
        self, mock_warmup, mock_clear
    ):
        """Transition away from published must invalidate published cache entries."""
        self.published_collection.publication_status = "private"
        self.published_collection.save(update_fields=["publication_status"])

        mock_clear.assert_called_once_with("collection_geojson:*")
        mock_warmup.assert_called_once()

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    @patch("sources.waste_collection.signals._schedule_cache_warmup")
    def test_cache_not_cleared_on_private_save_with_geojson_affecting_field(
        self, mock_warmup, mock_clear
    ):
        """Private GeoJSON-affecting updates should not flush global published cache."""
        self.private_collection.description = "Updated description"
        self.private_collection.save(update_fields=["description"])

        mock_clear.assert_not_called()
        mock_warmup.assert_not_called()

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    def test_cache_not_cleared_on_valid_until_update(self, mock_clear):
        """Verify cache is NOT cleared for valid_until updates."""
        self.published_collection.valid_until = date(2024, 12, 31)
        self.published_collection.save(update_fields=["valid_until"])

        mock_clear.assert_not_called()

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    def test_cache_not_cleared_on_name_only_update(self, mock_clear):
        """Verify cache is NOT cleared for name-only updates."""
        self.published_collection.name = "New Name"
        self.published_collection.save(update_fields=["name"])

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
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_category=cls.category,
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

    @patch("sources.waste_collection.signals.clear_geojson_cache_pattern")
    def test_name_update_does_not_trigger_cache_invalidation(self, mock_clear):
        """Verify name updates via update_collection_names don't trigger cache clear."""
        Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2023, 1, 1),
        )
        Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2022, 1, 1),
        )

        mock_clear.reset_mock()

        self.system.name = "Updated System"
        self.system.save()

        self.assertEqual(mock_clear.call_count, 0)

    def test_update_collection_names_updates_all_collections_atomically(self):
        """All collection name updates from a single related-object save must be atomic."""
        c2 = Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2023, 1, 1),
        )
        c3 = Collection.objects.create(
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2022, 1, 1),
        )

        self.system.name = "Batch Updated System"
        self.system.save()

        for c in [self.collection, c2, c3]:
            c.refresh_from_db()
            self.assertIn("Batch Updated System", c.name)
