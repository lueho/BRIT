"""Tests for sources.waste_collection.tasks."""

from unittest.mock import ANY, Mock, PropertyMock, call, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

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

        with patch(
            "sources.waste_collection.tasks.exclude_published_predecessors",
            side_effect=lambda queryset: queryset,
        ):
            result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 3)
        self.assertEqual(result["cache_key"], "collection_geojson:key")
        mock_collection.objects.filter.assert_called_once_with(
            publication_status="published"
        )
        mock_serializer.assert_called_once_with(annotated_qs, many=True)
        mock_build_cache_key.assert_called_once_with(scope="published")
        self.assertEqual(
            mock_get_cache.return_value.set.call_args_list,
            [
                call(
                    "collection_geojson:key",
                    {"features": [1, 2, 3]},
                    timeout=ANY,
                ),
                call("collection_geojson:key:count", 3, timeout=ANY),
            ],
        )

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
    ):
        """The versioned key must be computed before the queryset is serialized.

        Otherwise a write landing between serialization and the version query
        stores stale geometry under the current dataset version.
        """
        filtered_qs = Mock()
        filtered_qs.select_related.return_value.annotate.return_value = Mock()
        mock_collection.objects.filter.return_value = filtered_qs
        data_access = PropertyMock(return_value={"features": []})
        type(mock_serializer.return_value).data = data_access

        order = Mock()
        order.attach_mock(mock_build_cache_key, "build_collection_cache_key")
        order.attach_mock(data_access, "data")

        with patch(
            "sources.waste_collection.tasks.exclude_published_predecessors",
            side_effect=lambda queryset: queryset,
        ):
            result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            order.mock_calls,
            [
                call.build_collection_cache_key(scope="published"),
                call.data(),
            ],
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

        result = warm_collection_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 1)
        payload = mock_get_cache.return_value.set.call_args_list[0].args[1]
        self.assertEqual(
            [feature["properties"]["id"] for feature in payload["features"]],
            [successor.pk],
        )
