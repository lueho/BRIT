"""
Management command to warm GeoJSON caches.

Usage:
    # Warm all caches
    python manage.py warm_geojson_cache

    # Warm only roadside trees cache
    python manage.py warm_geojson_cache --trees

    # Warm only collections cache
    python manage.py warm_geojson_cache --collections

    # Warm only NUTS regions cache
    python manage.py warm_geojson_cache --nuts

    # Warm only the largest Region geometries (the ones crawlers stall on)
    python manage.py warm_geojson_cache --regions --regions-limit 50

    # Run asynchronously via Celery
    python manage.py warm_geojson_cache --async
"""

from django.conf import settings
from django.contrib.gis.db.models.functions import NumPoints
from django.core.cache import caches
from django.core.management.base import BaseCommand

from maps.models import NutsRegion, Region
from maps.serializers import (
    NutsRegionGeometrySerializer,
    RegionGeoFeatureModelSerializer,
)
from maps.utils import get_region_cache_key
from sources.registry import get_source_domain_geojson_cache_warmers

# Number of largest regions to warm by default. The H27 "Client Request
# Interrupted" warnings come almost entirely from crawlers fetching the few
# very large overview regions (e.g. "Europe (NUTS)", "Waste Atlas Background"),
# so warming the heaviest geometries covers the expensive cases cheaply.
DEFAULT_REGIONS_LIMIT = 50


class Command(BaseCommand):
    help = "Warm GeoJSON caches to prevent timeout on first request"

    FLAG_TO_PLUGIN = {
        "trees": ("roadside_trees", "Roadside Trees"),
        "collections": ("waste_collection", "Waste Collections"),
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--trees",
            action="store_true",
            help="Warm only the roadside trees cache",
        )
        parser.add_argument(
            "--collections",
            action="store_true",
            help="Warm only the waste collections cache",
        )
        parser.add_argument(
            "--nuts",
            action="store_true",
            help="Warm only the NUTS regions cache",
        )
        parser.add_argument(
            "--regions",
            action="store_true",
            help="Warm only the (largest) Region GeoJSON cache",
        )
        parser.add_argument(
            "--regions-limit",
            type=int,
            default=DEFAULT_REGIONS_LIMIT,
            help=(
                "Number of largest regions (by geometry point count) to warm "
                f"(default: {DEFAULT_REGIONS_LIMIT})"
            ),
        )
        parser.add_argument(
            "--nuts-levels",
            type=str,
            default="0,1,2",
            help="Comma-separated list of NUTS levels to cache (default: 0,1,2)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of items to cache per type",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Run asynchronously via Celery (non-blocking)",
        )

    def handle(self, *args, **options):
        from maps.tasks import warm_all_geojson_caches

        warm_trees = options["trees"]
        warm_collections = options["collections"]
        warm_nuts = options["nuts"]
        warm_regions = options["regions"]
        run_async = options["run_async"]
        warmers_by_slug = dict(get_source_domain_geojson_cache_warmers())

        # If no flag specified, warm all
        if not (warm_trees or warm_collections or warm_nuts or warm_regions):
            warm_trees = True
            warm_collections = True
            warm_nuts = True
            warm_regions = True

        # Warm NUTS cache (synchronous only)
        if warm_nuts:
            self._warm_nuts_cache(options)

        # Warm Region cache (synchronous only)
        if warm_regions:
            self._warm_regions_cache(options)

        # Handle plugin cache warming
        if warm_trees and warm_collections and not run_async:
            # Warm all synchronously
            self.stdout.write("Warming all GeoJSON caches (synchronous)...")
            result = warm_all_geojson_caches.apply()
            results = result.get()
            self._report_results(results)
            return

        if warm_trees and warm_collections and run_async:
            # Warm all asynchronously
            self.stdout.write("Warming all GeoJSON caches (async via Celery)...")
            warm_all_geojson_caches.delay()
            self.stdout.write(
                self.style.SUCCESS("Tasks queued. Check Celery logs for progress.")
            )
            return

        # Individual cache warming
        if warm_trees:
            self._warm_selected_cache("trees", warmers_by_slug, run_async)

        if warm_collections:
            self._warm_selected_cache("collections", warmers_by_slug, run_async)

    def _warm_selected_cache(self, option_name, warmers_by_slug, run_async):
        slug, display_name = self.FLAG_TO_PLUGIN[option_name]
        task = warmers_by_slug.get(slug)
        if task is None:
            self.stdout.write(
                self.style.WARNING(f"{display_name}: skipped (plugin not installed)")
            )
            return
        self._warm_cache(display_name, task, run_async)

    def _warm_cache(self, name, task, run_async):
        if run_async:
            self.stdout.write(f"Queuing {name} cache warm-up (async)...")
            task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"{name} task queued. Check Celery logs.")
            )
        else:
            self.stdout.write(f"Warming {name} cache (synchronous)...")
            result = task.apply()
            data = result.get()
            self._report_single_result(name, data)

    def _report_single_result(self, name, data):
        if data.get("status") == "success":
            self.stdout.write(
                self.style.SUCCESS(
                    f"{name}: {data.get('features_count', 0):,} features cached"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"{name}: Failed - {data.get('error', 'Unknown')}")
            )

    def _report_results(self, results):
        for key, data in results.items():
            name = key.replace("_", " ").title()
            self._report_single_result(name, data)

    def _warm_nuts_cache(self, options):
        """Warm NUTS regions cache."""
        geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        nuts_levels = [int(level) for level in options["nuts_levels"].split(",")]
        limit = options["limit"]

        self.stdout.write("Warming up NUTS GeoJSON cache...")

        # Cache NUTS regions by level
        for level in nuts_levels:
            self.stdout.write(f"Caching NUTS level {level} regions...")
            queryset = NutsRegion.objects.filter(levl_code=level)
            if limit:
                queryset = queryset[:limit]

            for region in queryset:
                cache_key = f"nuts_geojson:level:{level}:id:{region.id}"
                serializer = NutsRegionGeometrySerializer([region], many=True)
                geojson_cache.set(cache_key, serializer.data)

            # Also cache the collection
            cache_key = f"nuts_geojson:level:{level}"
            serializer = NutsRegionGeometrySerializer(queryset, many=True)
            geojson_cache.set(cache_key, serializer.data)

        self.stdout.write("NUTS cache warmup complete!")

    def _warm_regions_cache(self, options):
        """Warm the Region GeoJSON cache for the largest geometries.

        Region GeoJSON is requested per ``id`` (``region_geojson:id:<id>``), so
        the heavy overview regions are serialized fresh on every cold cache.
        Pre-warming the largest geometries turns those crawler hits into cache
        hits and avoids the multi-second responses that trigger H27 warnings.
        """
        cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
        geojson_cache = caches[cache_alias]
        # Mirror the viewset's cache timeout so warmed entries live exactly as
        # long as ones written by a normal request (default 24h for the geojson
        # cache) instead of relying on the backend's implicit default.
        timeout = settings.CACHES.get(cache_alias, {}).get("TIMEOUT", 3600)
        limit = options["limit"] or options["regions_limit"]

        self.stdout.write(f"Warming up Region GeoJSON cache (top {limit} largest)...")

        queryset = (
            Region.objects.select_related("borders")
            .filter(borders__isnull=False)
            .annotate(num_points=NumPoints("borders__geom"))
            .order_by("-num_points")[:limit]
        )

        warmed = 0
        for region in queryset:
            cache_key = get_region_cache_key(region_id=region.id)
            serializer = RegionGeoFeatureModelSerializer([region], many=True)
            geojson_cache.set(cache_key, serializer.data, timeout=timeout)
            warmed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Region cache warmup complete! ({warmed} regions)")
        )
