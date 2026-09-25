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

from django.core.management.base import BaseCommand

from maps.cache_warmup import (
    DEFAULT_REGIONS_LIMIT,
    warm_nuts_geojson_cache,
    warm_region_geojson_cache,
)
from maps.registry import get_source_domain_geojson_cache_warmers


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
        from maps.tasks import warm_all_geojson_caches, warm_base_geojson_caches

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

        warm_all = warm_trees and warm_collections and warm_nuts and warm_regions

        nuts_levels = [int(level) for level in options["nuts_levels"].split(",")]
        nuts_limit = options["limit"]
        regions_limit = options["limit"] or options["regions_limit"]

        # "Warm all" maps onto the umbrella task in both modes so that
        # synchronous and asynchronous runs warm exactly the same caches.
        if warm_all:
            task_kwargs = {
                "nuts_levels": nuts_levels,
                "nuts_limit": nuts_limit,
                "regions_limit": regions_limit,
            }
            if run_async:
                self.stdout.write("Warming all GeoJSON caches (async via Celery)...")
                warm_all_geojson_caches.delay(queue_subtasks=True, **task_kwargs)
                self.stdout.write(
                    self.style.SUCCESS("Tasks queued. Check Celery logs for progress.")
                )
            else:
                self.stdout.write("Warming all GeoJSON caches (synchronous)...")
                results = warm_all_geojson_caches.apply(kwargs=task_kwargs).get()
                self._report_results(results)
            return

        # Individual cache warming
        if warm_nuts or warm_regions:
            if run_async:
                self.stdout.write("Queuing base GeoJSON cache warm-up (async)...")
                warm_base_geojson_caches.delay(
                    nuts_levels=nuts_levels if warm_nuts else None,
                    regions_limit=regions_limit if warm_regions else None,
                    nuts_limit=nuts_limit if warm_nuts else None,
                )
                self.stdout.write(self.style.SUCCESS("Task queued. Check Celery logs."))
            else:
                if warm_nuts:
                    self._warm_nuts_cache(nuts_levels, options["limit"])
                if warm_regions:
                    self._warm_regions_cache(regions_limit)

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
            if isinstance(data, dict) and all(
                isinstance(v, dict) for v in data.values()
            ):
                # Nested result group (e.g. the base "maps" warmup)
                for sub_key, sub_data in data.items():
                    self._report_single_result(
                        f"{name} {sub_key.replace('_', ' ').title()}", sub_data
                    )
            else:
                self._report_single_result(name, data)

    def _warm_nuts_cache(self, nuts_levels, limit):
        self.stdout.write("Warming up NUTS GeoJSON cache...")
        result = warm_nuts_geojson_cache(nuts_levels=nuts_levels, limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"NUTS cache warmup complete! ({result['features_count']} entries)"
            )
        )

    def _warm_regions_cache(self, limit):
        self.stdout.write(f"Warming up Region GeoJSON cache (top {limit} largest)...")
        result = warm_region_geojson_cache(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Region cache warmup complete! ({result['features_count']} regions)"
            )
        )
