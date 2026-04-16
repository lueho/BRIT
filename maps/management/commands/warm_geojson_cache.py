"""
Management command to warm GeoJSON caches.

Usage:
    # Warm all caches
    python manage.py warm_geojson_cache

    # Warm only roadside trees cache
    python manage.py warm_geojson_cache --trees

    # Warm only collections cache
    python manage.py warm_geojson_cache --collections

    # Run asynchronously via Celery
    python manage.py warm_geojson_cache --async
"""

from django.core.management.base import BaseCommand

from sources.registry import get_source_domain_geojson_cache_warmers


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
            "--async",
            action="store_true",
            dest="run_async",
            help="Run asynchronously via Celery (non-blocking)",
        )

    def handle(self, *args, **options):
        from maps.tasks import warm_all_geojson_caches

        warm_trees = options["trees"]
        warm_collections = options["collections"]
        run_async = options["run_async"]
        warmers_by_slug = dict(get_source_domain_geojson_cache_warmers())

        # If neither flag specified, warm all
        if not warm_trees and not warm_collections:
            warm_trees = True
            warm_collections = True

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
                    f"{name}: {data.get("features_count", 0):,} features cached"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"{name}: Failed - {data.get("error", "Unknown")}")
            )

    def _report_results(self, results):
        for key, data in results.items():
            name = key.replace("_", " ").title()
            self._report_single_result(name, data)
