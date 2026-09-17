"""
Celery tasks for maps app.

Provides orchestration for GeoJSON cache warming.
"""

import logging

from celery import shared_task

from maps.cache_warmup import (
    DEFAULT_NUTS_LEVELS,
    DEFAULT_REGIONS_LIMIT,
    warm_nuts_geojson_cache,
    warm_region_geojson_cache,
)
from maps.registry import get_source_domain_geojson_cache_warmers

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="warm_base_geojson_caches")
def warm_base_geojson_caches(self, nuts_levels=None, regions_limit=None):
    """
    Warm the base-map GeoJSON caches (NUTS regions and the largest Regions).

    Pass ``nuts_levels=None`` or ``regions_limit=None`` to skip the
    corresponding cache; passing both ``None`` makes the task a no-op.
    """
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


@shared_task(bind=True, name="warm_all_geojson_caches")
def warm_all_geojson_caches(self):
    """
    Warm all GeoJSON caches. Called periodically or after major data changes.
    """
    results = {}

    try:
        results["maps"] = warm_base_geojson_caches.apply(
            kwargs={
                "nuts_levels": list(DEFAULT_NUTS_LEVELS),
                "regions_limit": DEFAULT_REGIONS_LIMIT,
            }
        ).get()
    except Exception as e:
        logger.exception("Failed to warm base GeoJSON caches: %s", e)
        results["maps"] = {"status": "error", "error": str(e)}

    for slug, warmer in get_source_domain_geojson_cache_warmers():
        try:
            result = warmer.apply()
            results[slug] = result.get()
        except Exception as e:
            logger.exception("Failed to warm %s cache: %s", slug, e)
            results[slug] = {"status": "error", "error": str(e)}

    return results
