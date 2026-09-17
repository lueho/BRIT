"""
Celery tasks for maps app.

Provides orchestration for GeoJSON cache warming.
"""

import logging

from celery import shared_task
from celery.signals import worker_ready

from maps.cache_warmup import (
    DEFAULT_NUTS_LEVELS,
    DEFAULT_REGIONS_LIMIT,
    warm_nuts_geojson_cache,
    warm_region_geojson_cache,
)
from maps.registry import get_source_domain_geojson_cache_warmers

logger = logging.getLogger(__name__)


def _warm_base_geojson_caches(nuts_levels, regions_limit):
    """Warm the base-map GeoJSON caches (NUTS regions and largest Regions)."""
    results = {}
    if nuts_levels is not None:
        try:
            results["nuts"] = warm_nuts_geojson_cache(nuts_levels=nuts_levels)
        except Exception as e:
            logger.exception("Failed to warm NUTS GeoJSON cache: %s", e)
            results["nuts"] = {"status": "error", "error": str(e)}
    if regions_limit is not None:
        try:
            results["regions"] = warm_region_geojson_cache(limit=regions_limit)
        except Exception as e:
            logger.exception("Failed to warm Region GeoJSON cache: %s", e)
            results["regions"] = {"status": "error", "error": str(e)}
    return results


@shared_task(bind=True, name="warm_base_geojson_caches")
def warm_base_geojson_caches(self, nuts_levels=None, regions_limit=None):
    """
    Warm the base-map GeoJSON caches (NUTS regions and the largest Regions).

    Pass ``nuts_levels=None`` or ``regions_limit=None`` to skip the
    corresponding cache; passing both ``None`` makes the task a no-op.
    """
    return _warm_base_geojson_caches(nuts_levels, regions_limit)


@shared_task(bind=True, name="warm_all_geojson_caches")
def warm_all_geojson_caches(self):
    """
    Warm all GeoJSON caches. Called periodically or after major data changes.

    Sub-warmers are invoked synchronously via ``apply()``. Their results are
    read from the returned ``EagerResult`` attributes instead of ``.get()``,
    because Celery forbids blocking ``result.get()`` calls inside a running
    task.
    """
    results = {}

    try:
        results["maps"] = _warm_base_geojson_caches(
            nuts_levels=list(DEFAULT_NUTS_LEVELS),
            regions_limit=DEFAULT_REGIONS_LIMIT,
        )
    except Exception as e:
        logger.exception("Failed to warm base GeoJSON caches: %s", e)
        results["maps"] = {"status": "error", "error": str(e)}

    for slug, warmer in get_source_domain_geojson_cache_warmers():
        try:
            eager = warmer.apply()
            if eager.successful():
                results[slug] = eager.result
            else:
                results[slug] = {"status": "error", "error": str(eager.result)}
        except Exception as e:
            logger.exception("Failed to warm %s cache: %s", slug, e)
            results[slug] = {"status": "error", "error": str(e)}

    return results


@worker_ready.connect
def warm_geojson_caches_on_worker_ready(sender=None, **kwargs):
    """Queue a full GeoJSON warmup whenever a worker starts.

    This replaces queueing the warmup from the Heroku release phase: a task
    queued there can be consumed by a still-running *old* worker, which would
    warm caches with the previous release's code (or none at all for newly
    introduced caches). ``worker_ready`` fires only in the freshly started
    worker, so the warmup is guaranteed to run on the new release's code —
    on deploys and on routine dyno restarts alike.
    """
    warm_all_geojson_caches.apply_async(countdown=30)
