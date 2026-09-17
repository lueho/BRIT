from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.test import SimpleTestCase, TestCase

from maps.models import NutsRegion, NutsVintage, Region
from maps.tasks import warm_all_geojson_caches, warm_base_geojson_caches
from maps.utils import (
    compute_collection_dataset_version,
    get_nuts_region_cache_key,
    get_region_cache_key,
)


class GeoJSONCacheDependencyBoundaryTests(SimpleTestCase):
    @patch("maps.utils.import_module")
    def test_compute_collection_dataset_version_uses_sources_collection_adapter(
        self, mock_import_module
    ):
        mock_collection = Mock()
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
        mock_import_module.return_value = Mock(Collection=mock_collection)

        version = compute_collection_dataset_version(scope="published")

        self.assertEqual(len(version), 12)
        mock_collection.objects.all.assert_called_once_with()
        base_qs.filter.assert_called_once_with(publication_status="published")
        published_qs.aggregate.assert_called_once()

    @patch(
        "maps.utils.import_module",
        side_effect=ModuleNotFoundError("sources.waste_collection.geojson"),
    )
    def test_compute_collection_dataset_version_returns_empty_signature_without_plugin(
        self, _mock_import_module
    ):
        version = compute_collection_dataset_version(scope="published")

        self.assertEqual(len(version), 12)

    @patch("maps.tasks.warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_uses_plugin_declared_warmers(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmer
    ):
        base_result = Mock()
        base_result.get.return_value = {"status": "success"}
        mock_base_warmer.apply.return_value = base_result

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

    @patch("maps.tasks.warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_includes_base_caches(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmer
    ):
        mock_get_source_domain_geojson_cache_warmers.return_value = ()
        base_result = Mock()
        base_result.get.return_value = {
            "nuts": {"status": "success"},
            "regions": {"status": "success"},
        }
        mock_base_warmer.apply.return_value = base_result

        result = warm_all_geojson_caches.run()

        self.assertEqual(result["maps"]["nuts"]["status"], "success")
        mock_base_warmer.apply.assert_called_once()


class WarmBaseGeojsonCachesTaskTests(TestCase):
    def setUp(self):
        self.geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        self.geojson_cache.clear()
        self.vintage = NutsVintage.default()
        self.nuts_region = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=self.vintage,
        )
        region = Region(name="Warmable Region")
        region.geom = MultiPolygon(Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))))
        region.save()
        self.region = region

    def test_warms_nuts_and_region_caches(self):
        result = warm_base_geojson_caches.run(nuts_levels=[0], regions_limit=10)

        year = self.vintage.year
        self.assertIsNotNone(
            self.geojson_cache.get(get_nuts_region_cache_key(level=0, version=year))
        )
        self.assertIsNotNone(
            self.geojson_cache.get(get_region_cache_key(region_id=self.region.id))
        )
        self.assertEqual(result["nuts"]["status"], "success")
        self.assertEqual(result["regions"]["status"], "success")

    def test_skips_nuts_when_levels_is_none(self):
        result = warm_base_geojson_caches.run(nuts_levels=None, regions_limit=10)

        year = self.vintage.year
        self.assertIsNone(
            self.geojson_cache.get(get_nuts_region_cache_key(level=0, version=year))
        )
        self.assertIsNotNone(
            self.geojson_cache.get(get_region_cache_key(region_id=self.region.id))
        )
        self.assertNotIn("nuts", result)

    def test_skips_regions_when_limit_is_none(self):
        result = warm_base_geojson_caches.run(nuts_levels=[0], regions_limit=None)

        self.assertIsNone(
            self.geojson_cache.get(get_region_cache_key(region_id=self.region.id))
        )
        self.assertNotIn("regions", result)
