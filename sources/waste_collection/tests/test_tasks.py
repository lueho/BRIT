"""Tests for sources.waste_collection.tasks."""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from sources.waste_collection.models import WasteFlyer
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

    def test_cleanup_orphaned_waste_flyers_does_not_raise(self):
        """Calling the task should not raise a FieldError from an invalid reverse relation."""
        owner = get_user_model().objects.create(username="task_test_user")
        flyer = WasteFlyer.objects.create(
            url="https://www.example.com/orphan",
            owner=owner,
        )
        deleted_count, _ = cleanup_orphaned_waste_flyers()
        self.assertEqual(deleted_count, 1)
        self.assertFalse(WasteFlyer.objects.filter(pk=flyer.pk).exists())


class WasteCollectionGeoJSONWarmTaskTestCase(SimpleTestCase):
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
    ):
        filtered_qs = Mock()
        selected_qs = Mock()
        annotated_qs = Mock()
        mock_collection.objects.filter.return_value = filtered_qs
        filtered_qs.select_related.return_value = selected_qs
        selected_qs.annotate.return_value = annotated_qs
        mock_serializer.return_value.data = {"features": [1, 2, 3]}

        result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 3)
        self.assertEqual(result["cache_key"], "collection_geojson:key")
        mock_collection.objects.filter.assert_called_once_with(
            publication_status="published"
        )
        mock_serializer.assert_called_once_with(annotated_qs, many=True)
        mock_build_cache_key.assert_called_once_with(scope="published")
        mock_get_cache.return_value.set.assert_called_once()
