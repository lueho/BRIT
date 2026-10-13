"""Tests for sources.waste_collection.tasks."""

import json
import zlib
from datetime import timedelta
from unittest.mock import ANY, Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from materials.models import Material, Sample, SampleExternalRecord
from processes.models import Process
from sources.waste_collection.models import (
    Catchment,
    Collection,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteFlyer,
)
from sources.waste_collection.tasks import (
    cleanup_orphaned_waste_flyers,
    warm_collection_geojson_cache,
)

from .test_views import (  # noqa: F401
    CheckWasteFlyerUrlsTestCase,
    CheckWasteFlyerUrlWaybackFallbackTestCase,
)


class CleanupOrphanedWasteFlyersTestCase(TestCase):
    """Test cleanup_orphaned_waste_flyers task does not raise FieldError."""

    def _backdate(self, flyer, days=8):
        WasteFlyer.objects.filter(pk=flyer.pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def _orphan_flyer(self, owner, **kwargs):
        flyer = WasteFlyer.objects.create(owner=owner, **kwargs)
        self._backdate(flyer)
        return flyer

    def test_cleanup_orphaned_waste_flyers_does_not_raise(self):
        """Calling the task should not raise a FieldError from an invalid reverse relation."""
        owner = get_user_model().objects.create(username="task_test_user")
        flyer = self._orphan_flyer(
            owner,
            url="https://www.example.com/orphan",
        )
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 1)
        self.assertFalse(WasteFlyer.objects.filter(pk=flyer.pk).exists())

    def test_recently_created_flyer_is_not_deleted(self):
        """A flyer within the grace period is kept so it can still be linked."""
        owner = get_user_model().objects.create(username="grace_user")
        flyer = WasteFlyer.objects.create(
            url="https://www.example.com/fresh",
            owner=owner,
        )
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 0)
        self.assertTrue(WasteFlyer.objects.filter(pk=flyer.pk).exists())

    def test_flyer_cited_by_process_is_not_deleted(self):
        owner = get_user_model().objects.create(username="process_cite_user")
        flyer = self._orphan_flyer(owner, url="https://www.example.com/process")
        process = Process.objects.create(name="Test process", owner=owner)
        process.sources.add(flyer)
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 0)
        self.assertTrue(WasteFlyer.objects.filter(pk=flyer.pk).exists())

    def test_flyer_cited_by_sample_is_not_deleted(self):
        owner = get_user_model().objects.create(username="sample_cite_user")
        flyer = self._orphan_flyer(owner, url="https://www.example.com/sample")
        material = Material.objects.create(name="Test material", owner=owner)
        sample = Sample.objects.create(
            name="Test sample", material=material, owner=owner
        )
        sample.sources.add(flyer)
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 0)
        self.assertTrue(WasteFlyer.objects.filter(pk=flyer.pk).exists())

    def test_flyer_cited_by_external_sample_record_is_not_deleted(self):
        """A PROTECTed FK citation must keep the flyer instead of aborting the delete."""
        owner = get_user_model().objects.create(username="record_cite_user")
        flyer = self._orphan_flyer(owner, url="https://www.example.com/record")
        material = Material.objects.create(name="Record material", owner=owner)
        sample = Sample.objects.create(
            name="Record sample", material=material, owner=owner
        )
        SampleExternalRecord.objects.create(
            sample=sample, source=flyer, external_id="1"
        )
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 0)
        self.assertTrue(WasteFlyer.objects.filter(pk=flyer.pk).exists())


class CleanupOrphanedWasteFlyersScheduleTestCase(SimpleTestCase):
    """Orphaned flyers also arise outside the collection form (API mutations,
    imports), so the cleanup must run periodically, not only on form saves."""

    def test_cleanup_task_is_on_the_beat_schedule(self):
        scheduled_tasks = {
            entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
        }
        self.assertIn("cleanup_orphaned_waste_flyers", scheduled_tasks)


class WasteCollectionGeoJSONWarmTaskTestCase(SimpleTestCase):
    @staticmethod
    def queryset(mock_collection, count):
        queryset = mock_collection.objects.filter.return_value.select_related.return_value.annotate.return_value
        queryset.aggregate.return_value = {
            "cnt": count,
            "min_id": 1,
            "max_id": count,
            "max_mod": None,
            "max_region_mod": None,
            "num_points": 0,
        }
        return queryset

    @patch("sources.waste_collection.tasks.cache_rendered_geojson", return_value=True)
    @patch("sources.waste_collection.tasks.get_geojson_cache")
    @patch(
        "sources.waste_collection.tasks.build_collection_cache_key",
        return_value="collection_geojson:key",
    )
    @patch("sources.waste_collection.tasks.WasteCollectionGeometrySerializer")
    @patch("sources.waste_collection.tasks.Collection")
    def test_warm_collection_geojson_cache_uses_source_owned_adapter(
        self,
        mock_collection,
        mock_serializer,
        mock_build_cache_key,
        mock_get_cache,
        mock_render,
    ):
        queryset = self.queryset(mock_collection, 3)
        mock_get_cache.return_value.has_key.return_value = False
        with patch(
            "sources.waste_collection.tasks.exclude_published_predecessors",
            side_effect=lambda queryset: queryset,
        ):
            result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 3)
        self.assertTrue(
            result["cache_key"].startswith("collection_geojson:key:json:v2:")
        )
        mock_collection.objects.filter.assert_called_once_with(
            publication_status="published"
        )
        mock_serializer.assert_not_called()
        mock_build_cache_key.assert_called_once_with(scope="published")
        mock_render.assert_called_once_with(
            mock_get_cache.return_value,
            result["cache_key"],
            queryset,
            mock_serializer,
            "simplified_geom",
            timeout=ANY,
            geometry_defer_field="catchment__region__borders__geom",
        )

    @patch("sources.waste_collection.tasks.cache_rendered_geojson", return_value=True)
    @patch("sources.waste_collection.tasks.get_geojson_cache")
    @patch(
        "sources.waste_collection.tasks.build_collection_cache_key",
        return_value="collection_geojson:key",
    )
    @patch("sources.waste_collection.tasks.WasteCollectionGeometrySerializer")
    @patch("sources.waste_collection.tasks.Collection")
    def test_warm_computes_versioned_key_before_serializing(
        self,
        mock_collection,
        mock_serializer,
        mock_build_cache_key,
        mock_get_cache,
        mock_render,
    ):
        """The versioned key must be computed before the queryset is serialized.

        Otherwise a write landing between serialization and the version query
        stores stale geometry under the current dataset version.
        """
        self.queryset(mock_collection, 0)
        mock_get_cache.return_value.has_key.return_value = False
        order = Mock()
        order.attach_mock(mock_build_cache_key, "build_collection_cache_key")
        order.attach_mock(mock_render, "render")
        with patch(
            "sources.waste_collection.tasks.exclude_published_predecessors",
            side_effect=lambda queryset: queryset,
        ):
            result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            [event[0] for event in order.mock_calls],
            ["build_collection_cache_key", "render"],
        )


class WasteCollectionGeoJSONWarmTaskQuerysetTestCase(TestCase):
    @patch("sources.waste_collection.tasks.get_geojson_cache")
    def test_warmup_excludes_published_predecessors(self, mock_get_cache):
        owner = get_user_model().objects.create(username="geojson_warmup_owner")
        catchment = Catchment.objects.create(name="Warmup catchment")
        collector = Collector.objects.create(name="Warmup collector")
        fee_system = FeeSystem.objects.create(name="Warmup fee system")
        frequency = CollectionFrequency.objects.create(name="Warmup frequency")
        collection_system = CollectionSystem.objects.create(name="Warmup system")
        waste_category = WasteCategory.objects.create(name="Warmup category")
        fields = {
            "owner": owner,
            "catchment": catchment,
            "collector": collector,
            "fee_system": fee_system,
            "frequency": frequency,
            "collection_system": collection_system,
            "waste_category": waste_category,
            "publication_status": "published",
        }
        predecessor = Collection.objects.create(name="Old version", **fields)
        successor = Collection.objects.create(name="Current version", **fields)
        successor.predecessors.add(predecessor)
        mock_get_cache.return_value.has_key.return_value = False

        result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 1)
        payload = mock_get_cache.return_value.set.call_args_list[0].args[1]
        self.assertIsInstance(payload, bytes)
        payload = json.loads(zlib.decompress(payload))
        self.assertEqual(
            [feature["properties"]["id"] for feature in payload["features"]],
            [successor.pk],
        )
