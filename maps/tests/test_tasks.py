from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from maps.tasks import warm_all_geojson_caches
from maps.utils import compute_collection_dataset_version


class GeoJSONCacheDependencyBoundaryTests(SimpleTestCase):
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

    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_uses_plugin_declared_warmers(
        self, mock_get_source_domain_geojson_cache_warmers
    ):
        collection_result = Mock()
        collection_result.get.return_value = {"status": "success", "features_count": 3}
        collection_warmer = Mock()
        collection_warmer.apply.return_value = collection_result

        tree_result = Mock()
        tree_result.get.return_value = {"status": "success", "features_count": 2}
        tree_warmer = Mock()
        tree_warmer.apply.return_value = tree_result

        mock_get_source_domain_geojson_cache_warmers.return_value = (
            ("roadside_trees", tree_warmer),
            ("waste_collection", collection_warmer),
        )

        result = warm_all_geojson_caches.run()

        self.assertEqual(result["roadside_trees"]["features_count"], 2)
        self.assertEqual(result["waste_collection"]["features_count"], 3)
        tree_warmer.apply.assert_called_once_with()
        collection_warmer.apply.assert_called_once_with()
