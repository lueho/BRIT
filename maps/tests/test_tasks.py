from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from maps.tasks import warm_collection_geojson_cache, warm_roadside_tree_geojson_cache
from maps.utils import compute_collection_dataset_version


class GeoJSONCacheDependencyBoundaryTests(SimpleTestCase):
    @patch("maps.tasks.get_geojson_cache")
    @patch("maps.utils.build_collection_cache_key", return_value="collection_geojson:key")
    @patch("sources.waste_collection.geojson.WasteCollectionGeometrySerializer")
    @patch("sources.waste_collection.geojson.Collection")
    def test_warm_collection_geojson_cache_uses_sources_adapter(
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

    @patch("maps.tasks.get_geojson_cache")
    @patch("sources.roadside_trees.geojson.HamburgRoadsideTreeGeometrySerializer")
    @patch("sources.roadside_trees.geojson.HamburgRoadsideTrees")
    def test_warm_roadside_tree_geojson_cache_uses_sources_adapter(
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

    @patch("sources.waste_collection.geojson.Collection")
    def test_compute_collection_dataset_version_uses_sources_collection_adapter(
        self, mock_collection
    ):
        base_qs = Mock()
        published_qs = Mock()
        mock_collection.objects.all.return_value = base_qs
        base_qs.filter.return_value = published_qs
        published_qs.aggregate.return_value = {
            "cnt": 3,
            "max_mod": None,
            "min_id": 4,
            "max_id": 9,
        }

        version = compute_collection_dataset_version(scope="published")

        self.assertEqual(len(version), 12)
        mock_collection.objects.all.assert_called_once_with()
        base_qs.filter.assert_called_once_with(publication_status="published")
        published_qs.aggregate.assert_called_once()
