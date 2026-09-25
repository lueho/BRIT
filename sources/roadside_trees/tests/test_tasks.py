from unittest.mock import ANY, Mock, PropertyMock, call, patch

from django.test import SimpleTestCase

from sources.roadside_trees.tasks import warm_roadside_tree_geojson_cache


class RoadsideTreesGeoJSONWarmTaskTestCase(SimpleTestCase):
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeGeometrySerializer")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTrees")
    def test_warm_roadside_tree_geojson_cache_uses_source_owned_adapter(
        self,
        mock_trees,
        mock_serializer,
        mock_get_cache,
        mock_viewset,
    ):
        only_qs = Mock()
        ordered_qs = Mock()
        mock_trees.objects.only.return_value = only_qs
        only_qs.order_by.return_value = ordered_qs
        mock_serializer.return_value.data = {"features": [1, 2]}
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 2,
            "version": "dv123",
        }

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 2)
        self.assertEqual(result["cache_key"], "tree_geojson:all:dv:dv123")
        mock_viewset.return_value.get_dataset_stats.assert_called_once_with(None)
        mock_trees.objects.only.assert_called_once_with("id", "geom")
        only_qs.order_by.assert_called_once_with()
        mock_serializer.assert_called_once_with(ordered_qs, many=True)
        self.assertEqual(
            mock_get_cache.return_value.set.call_args_list,
            [
                call(
                    "tree_geojson:all:dv:dv123",
                    {"features": [1, 2]},
                    timeout=ANY,
                ),
                call("tree_geojson:all:dv:dv123:count", 2, timeout=ANY),
            ],
        )

    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeGeometrySerializer")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTrees")
    def test_warm_captures_dataset_version_before_serializing(
        self,
        mock_trees,
        mock_serializer,
        mock_get_cache,
        mock_viewset,
    ):
        """The version must be read before the queryset is serialized.

        Otherwise an external write landing between serialization and the
        stats query stores stale geometry under the current versioned key.
        """
        mock_trees.objects.only.return_value.order_by.return_value = Mock()
        data_access = PropertyMock(return_value={"features": []})
        type(mock_serializer.return_value).data = data_access
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 2,
            "version": "dv123",
        }

        order = Mock()
        order.attach_mock(
            mock_viewset.return_value.get_dataset_stats, "get_dataset_stats"
        )
        order.attach_mock(data_access, "data")

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            order.mock_calls,
            [call.get_dataset_stats(None), call.data()],
        )

    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeViewSet")
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeGeometrySerializer")
    def test_large_dataset_is_skipped_before_serialization(
        self, mock_serializer, mock_get_cache, mock_viewset
    ):
        mock_viewset.return_value.get_dataset_stats.return_value = {
            "count": 230615,
            "version": "dv123",
        }

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["features_count"], 230615)
        mock_serializer.assert_not_called()
        mock_get_cache.assert_not_called()
