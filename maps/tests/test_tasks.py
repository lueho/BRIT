from unittest.mock import Mock, patch

from celery.result import EagerResult
from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.test import SimpleTestCase, TestCase

from maps.models import NutsRegion, NutsVintage, Region
from maps.tasks import (
    STARTUP_WARMUP_FLAG_CACHE_KEY,
    warm_all_geojson_caches,
    warm_base_geojson_caches,
    warm_geojson_caches_on_worker_ready,
)
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

    @patch("maps.tasks._warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_uses_plugin_declared_warmers(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmup
    ):
        mock_base_warmup.return_value = {"status": "success"}

        collection_warmer = Mock()
        collection_warmer.apply.return_value = EagerResult(
            "collection-task",
            {"status": "success", "features_count": 3},
            "SUCCESS",
        )

        tree_warmer = Mock()
        tree_warmer.apply.return_value = EagerResult(
            "tree-task",
            {"status": "success", "features_count": 2},
            "SUCCESS",
        )

        mock_get_source_domain_geojson_cache_warmers.return_value = (
            ("roadside_trees", tree_warmer),
            ("waste_collection", collection_warmer),
        )

        result = warm_all_geojson_caches.run()

        self.assertEqual(result["roadside_trees"]["features_count"], 2)
        self.assertEqual(result["waste_collection"]["features_count"], 3)
        tree_warmer.apply.assert_called_once_with()
        collection_warmer.apply.assert_called_once_with()

    @patch("maps.tasks._warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_includes_base_caches(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmup
    ):
        mock_get_source_domain_geojson_cache_warmers.return_value = ()
        mock_base_warmup.return_value = {
            "nuts": {"status": "success"},
            "regions": {"status": "success"},
        }

        result = warm_all_geojson_caches.run()

        self.assertEqual(result["maps"]["nuts"]["status"], "success")
        mock_base_warmup.assert_called_once()

    @patch("maps.tasks._warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_forwards_cli_overrides(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmup
    ):
        mock_get_source_domain_geojson_cache_warmers.return_value = ()
        mock_base_warmup.return_value = {"status": "success"}

        warm_all_geojson_caches.run(nuts_levels=[0], nuts_limit=10, regions_limit=5)

        mock_base_warmup.assert_called_once_with(
            nuts_levels=[0], regions_limit=5, nuts_limit=10
        )

    @patch("maps.tasks._warm_base_geojson_caches")
    @patch("maps.tasks.get_source_domain_geojson_cache_warmers")
    def test_warm_all_geojson_caches_never_calls_result_get_inside_task(
        self, mock_get_source_domain_geojson_cache_warmers, mock_base_warmup
    ):
        """Inside a running task, EagerResult.get() raises RuntimeError.

        The umbrella task must read sub-results without ``get()``; this test
        simulates a real worker context where blocking calls are forbidden.
        """
        mock_base_warmup.return_value = {"status": "success"}
        warmer = Mock()
        warmer.apply.return_value = EagerResult(
            "task", {"status": "success", "features_count": 1}, "SUCCESS"
        )
        mock_get_source_domain_geojson_cache_warmers.return_value = (
            ("roadside_trees", warmer),
        )

        with patch("celery.result.task_join_will_block", return_value=True):
            result = warm_all_geojson_caches.run()

        self.assertEqual(result["roadside_trees"]["features_count"], 1)


class WorkerReadyWarmupTaskTests(TestCase):
    def setUp(self):
        self.geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        self.geojson_cache.delete(STARTUP_WARMUP_FLAG_CACHE_KEY)

    def tearDown(self):
        self.geojson_cache.delete(STARTUP_WARMUP_FLAG_CACHE_KEY)

    @patch("maps.tasks.warm_all_geojson_caches")
    def test_worker_ready_queues_full_geojson_warmup(self, mock_warm_all):
        warm_geojson_caches_on_worker_ready()

        mock_warm_all.apply_async.assert_called_once_with(countdown=30)

    @patch("maps.tasks.warm_all_geojson_caches")
    def test_worker_ready_does_not_requeue_within_cooldown(self, mock_warm_all):
        """A crash restart re-fires worker_ready; the flag must suppress
        re-queueing so a failing warmup cannot crash-loop the dyno."""
        warm_geojson_caches_on_worker_ready()
        warm_geojson_caches_on_worker_ready()

        mock_warm_all.apply_async.assert_called_once_with(countdown=30)


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

    def test_skips_regions_over_point_budget(self):
        """Serializing a multi-hundred-thousand-point geometry OOMs the
        worker dyno; oversized regions must be skipped, not warmed."""
        with patch("maps.cache_warmup.REGION_GEOJSON_WARMUP_MAX_POINTS", 4):
            result = warm_base_geojson_caches.run(nuts_levels=None, regions_limit=10)

        self.assertIsNone(
            self.geojson_cache.get(get_region_cache_key(region_id=self.region.id))
        )
        self.assertEqual(result["regions"]["status"], "success")
        self.assertEqual(result["regions"]["features_count"], 0)
        self.assertEqual(result["regions"]["skipped"][0]["id"], self.region.id)

    def test_nuts_limit_slices_per_level_queryset(self):
        NutsRegion.objects.create(
            name="Luxembourg",
            nuts_id="LU",
            levl_code=0,
            cntr_code="LU",
            version=self.vintage,
        )

        result = warm_base_geojson_caches.run(
            nuts_levels=[0], regions_limit=None, nuts_limit=1
        )

        self.assertEqual(result["nuts"]["features_count"], 1)
