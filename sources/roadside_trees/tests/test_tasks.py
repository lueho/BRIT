from unittest.mock import ANY, Mock, call, patch

from django.test import SimpleTestCase

from maps.utils import rendered_geojson_cache_key
from sources.roadside_trees.tasks import warm_roadside_tree_geojson_cache


class RoadsideTreesGeoJSONWarmTaskTestCase(SimpleTestCase):
    @patch("sources.roadside_trees.tasks.cache_rendered_geojson")
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTrees")
    def test_warm_roadside_tree_geojson_cache_uses_source_owned_adapter(
        self,
        mock_trees,
        mock_viewset,
        mock_get_cache,
        mock_render,
    ):
        only_qs = Mock()
        ordered_qs = Mock()
        mock_trees.objects.only.return_value = only_qs
        only_qs.order_by.return_value = ordered_qs
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 2,
            "version": "dv123",
        }
        mock_get_cache.return_value.has_key.return_value = False
        mock_render.return_value = True

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 2)
        base_key = "tree_geojson:all:dv:dv123"
        rendered_key = rendered_geojson_cache_key(base_key, "dv123")
        self.assertEqual(result["cache_key"], rendered_key)
        mock_viewset.return_value.get_dataset_stats.assert_called_once_with(None)
        mock_trees.objects.only.assert_called_once_with("id", "geom")
        only_qs.order_by.assert_called_once_with()
        mock_render.assert_called_once_with(
            mock_get_cache.return_value,
            rendered_key,
            ordered_qs,
            ANY,
            "geom",
            timeout=ANY,
        )
        # Drop the legacy serializer-payload entry under the same version:
        # the rendered path only reads the rendered key.
        mock_get_cache.return_value.delete.assert_has_calls(
            [call(base_key), call(f"{base_key}:count")]
        )

    @patch("sources.roadside_trees.tasks.cache_rendered_geojson")
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTrees")
    def test_warm_captures_dataset_version_before_serializing(
        self,
        mock_trees,
        mock_viewset,
        mock_get_cache,
        mock_render,
    ):
        """The version must be read before the queryset is rendered.

        Otherwise an external write landing between serialization and the
        stats query stores stale geometry under the current versioned key.
        """
        mock_trees.objects.only.return_value.order_by.return_value = Mock()
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 2,
            "version": "dv123",
        }
        mock_get_cache.return_value.has_key.return_value = False
        mock_render.return_value = True

        order = Mock()
        order.attach_mock(
            mock_viewset.return_value.get_dataset_stats, "get_dataset_stats"
        )
        order.attach_mock(mock_render, "render")

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            order.mock_calls,
            [
                call.get_dataset_stats(None),
                call.render(ANY, ANY, ANY, ANY, "geom", timeout=ANY),
            ],
        )

    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    def test_large_dataset_is_skipped_before_serialization(
        self, mock_viewset, mock_get_cache
    ):
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 230615,
            "version": "dv123",
        }

        with self.assertLogs("sources.roadside_trees.tasks", level="WARNING") as logs:
            result = warm_roadside_tree_geojson_cache.run()
        self.assertIn("features exceed", logs.output[0])

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["features_count"], 230615)
        mock_get_cache.assert_not_called()
