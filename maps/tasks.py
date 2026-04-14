"""
Celery tasks for maps app.

Provides orchestration for GeoJSON cache warming.
"""

import logging

from celery import shared_task

from sources.registry import get_source_domain_geojson_cache_warmers

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="warm_all_geojson_caches")
def warm_all_geojson_caches(self):
    """
    Warm all GeoJSON caches. Called periodically or after major data changes.
    """
    results = {}

    for slug, warmer in get_source_domain_geojson_cache_warmers():
        try:
            result = warmer.apply()
            results[slug] = result.get()
        except Exception as e:
            logger.exception("Failed to warm %s cache: %s", slug, e)
            results[slug] = {"status": "error", "error": str(e)}

    return results
