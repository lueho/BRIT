import io
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.core.management import call_command
from django.test import TestCase

from ..models import (
    NutsRegion,
    NutsVintage,
    Region,
)
from ..utils import get_nuts_region_cache_key, get_region_cache_key


class WarmGeojsonCacheCommandTests(TestCase):
    @patch(
        "maps.management.commands.warm_geojson_cache.get_source_domain_geojson_cache_warmers"
    )
    def test_selected_missing_plugin_is_skipped_without_error(self, mock_get_warmers):
        out = io.StringIO()
        mock_get_warmers.return_value = ()

        call_command("warm_geojson_cache", trees=True, stdout=out)

        self.assertIn("Roadside Trees: skipped (plugin not installed)", out.getvalue())

    @patch(
        "maps.management.commands.warm_geojson_cache.get_source_domain_geojson_cache_warmers"
    )
    def test_selected_registered_plugin_uses_registry_warmer(self, mock_get_warmers):
        out = io.StringIO()
        result = Mock()
        result.get.return_value = {"status": "success", "features_count": 2}
        warmer = Mock()
        warmer.apply.return_value = result
        mock_get_warmers.return_value = (("roadside_trees", warmer),)

        call_command("warm_geojson_cache", trees=True, stdout=out)

        warmer.apply.assert_called_once_with()
        self.assertIn("Roadside Trees: 2 features cached", out.getvalue())

    @patch("maps.tasks.warm_base_geojson_caches")
    @patch("maps.tasks.warm_all_geojson_caches")
    def test_async_flag_queues_umbrella_task_for_all_caches(
        self, mock_warm_all, mock_warm_base
    ):
        out = io.StringIO()

        call_command("warm_geojson_cache", run_async=True, stdout=out)

        mock_warm_all.delay.assert_called_once_with(
            nuts_levels=[0, 1, 2],
            nuts_limit=None,
            regions_limit=50,
            queue_subtasks=True,
        )
        mock_warm_base.delay.assert_not_called()
        self.assertIn("queued", out.getvalue().lower())

    @patch("maps.tasks.warm_all_geojson_caches")
    def test_limit_and_nuts_levels_reach_umbrella_task(self, mock_warm_all):
        out = io.StringIO()

        call_command(
            "warm_geojson_cache",
            limit=10,
            nuts_levels="0",
            run_async=True,
            stdout=out,
        )

        mock_warm_all.delay.assert_called_once_with(
            nuts_levels=[0], nuts_limit=10, regions_limit=10, queue_subtasks=True
        )

    @patch("maps.tasks.warm_all_geojson_caches")
    def test_regions_limit_reaches_umbrella_task(self, mock_warm_all):
        out = io.StringIO()

        call_command("warm_geojson_cache", regions_limit=5, run_async=True, stdout=out)

        mock_warm_all.delay.assert_called_once_with(
            nuts_levels=[0, 1, 2],
            nuts_limit=None,
            regions_limit=5,
            queue_subtasks=True,
        )

    @patch("maps.tasks.warm_base_geojson_caches")
    def test_async_flag_queues_base_task_for_nuts(self, mock_warm_base):
        out = io.StringIO()

        call_command("warm_geojson_cache", nuts=True, run_async=True, stdout=out)

        mock_warm_base.delay.assert_called_once_with(
            nuts_levels=[0, 1, 2], regions_limit=None, nuts_limit=None
        )

    @patch("maps.tasks.warm_base_geojson_caches")
    def test_async_flag_forwards_limit_for_nuts(self, mock_warm_base):
        out = io.StringIO()

        call_command(
            "warm_geojson_cache",
            nuts=True,
            limit=10,
            run_async=True,
            stdout=out,
        )

        mock_warm_base.delay.assert_called_once_with(
            nuts_levels=[0, 1, 2], regions_limit=None, nuts_limit=10
        )

    @patch("maps.tasks.warm_base_geojson_caches")
    def test_async_flag_queues_base_task_for_regions(self, mock_warm_base):
        out = io.StringIO()

        call_command(
            "warm_geojson_cache",
            regions=True,
            regions_limit=5,
            run_async=True,
            stdout=out,
        )

        mock_warm_base.delay.assert_called_once_with(
            nuts_levels=None, regions_limit=5, nuts_limit=None
        )


class WarmGeojsonCacheRegionsTests(TestCase):
    def setUp(self):
        self.geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        self.geojson_cache.clear()

    @staticmethod
    def _make_region(name, num_vertices=4):
        # Build a closed ring with the requested number of distinct vertices so
        # regions can be ordered by geometry point count.
        ring = [(0, 0)]
        ring += [(i + 1, (i % 2) + 1) for i in range(max(num_vertices - 1, 1))]
        ring.append((0, 0))
        region = Region(name=name)
        region.geom = MultiPolygon(Polygon(tuple(ring)))
        region.save()
        return region

    def test_regions_flag_warms_largest_region_geojson_cache(self):
        region = self._make_region("Warmed Region")
        out = io.StringIO()

        call_command("warm_geojson_cache", regions=True, regions_limit=10, stdout=out)

        cached = self.geojson_cache.get(get_region_cache_key(region_id=region.id))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached["features"]), 1)
        self.assertIn("Region cache warmup complete!", out.getvalue())

    def test_regions_limit_only_warms_largest_regions(self):
        big = self._make_region("Big Region", num_vertices=20)
        small = self._make_region("Small Region", num_vertices=4)
        out = io.StringIO()

        call_command("warm_geojson_cache", regions=True, regions_limit=1, stdout=out)

        self.assertIsNotNone(
            self.geojson_cache.get(get_region_cache_key(region_id=big.id))
        )
        self.assertIsNone(
            self.geojson_cache.get(get_region_cache_key(region_id=small.id))
        )


class WarmGeojsonCacheNutsTests(TestCase):
    """Warmed NUTS entries must land where the viewset looks for them."""

    def setUp(self):
        self.geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        self.geojson_cache.clear()
        self.vintage = NutsVintage.default()
        self.region = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=self.vintage,
        )

    def test_warmed_keys_carry_the_vintage_the_viewset_asks_for(self):
        call_command(
            "warm_geojson_cache", nuts=True, nuts_levels="0", stdout=io.StringIO()
        )

        year = self.vintage.year
        self.assertIsNotNone(
            self.geojson_cache.get(get_nuts_region_cache_key(level=0, version=year))
        )
        self.assertIsNotNone(
            self.geojson_cache.get(
                get_nuts_region_cache_key(nuts_id=self.region.id, version=year)
            )
        )
