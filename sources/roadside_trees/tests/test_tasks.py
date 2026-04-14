from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from sources.roadside_trees.tasks import warm_roadside_tree_geojson_cache


class RoadsideTreesGeoJSONWarmTaskTestCase(SimpleTestCase):
    @patch("sources.roadside_trees.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTreeGeometrySerializer")
    @patch("sources.roadside_trees.tasks.HamburgRoadsideTrees")
    def test_warm_roadside_tree_geojson_cache_uses_source_owned_adapter(
        self,
        mock_trees,
        mock_serializer,
        mock_get_cache,
    ):
        only_qs = Mock()
        ordered_qs = Mock()
        mock_trees.objects.only.return_value = only_qs
        only_qs.order_by.return_value = ordered_qs
        mock_serializer.return_value.data = {"features": [1, 2]}

        result = warm_roadside_tree_geojson_cache.run()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["features_count"], 2)
        self.assertEqual(result["cache_key"], "tree_geojson:all")
        mock_trees.objects.only.assert_called_once_with("id", "geom")
        only_qs.order_by.assert_called_once_with()
        mock_serializer.assert_called_once_with(ordered_qs, many=True)
        mock_get_cache.return_value.set.assert_called_once()
