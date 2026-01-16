"""
Celery tasks for maps app.

Provides cache warming functionality for GeoJSON endpoints to prevent
timeout issues on first requests.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import caches

logger = logging.getLogger(__name__)


def get_geojson_cache():
    """Get the configured GeoJSON cache backend."""
    cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
    return caches[cache_alias]


@shared_task(bind=True, name="warm_collection_geojson_cache")
def warm_collection_geojson_cache(self):
    """
    Pre-warm the Collection GeoJSON cache for the published scope.

    This task should be triggered after Collection data changes to ensure
    the cache is populated before users request the data. This prevents
    H12 timeout errors on first requests.

    Uses simplified geometry to reduce cache size and improve performance.
    """
    from django.db.models import F

    from case_studies.soilcom.models import Collection
    from case_studies.soilcom.serializers import (
        GEOMETRY_SIMPLIFY_TOLERANCE,
        WasteCollectionGeometrySerializer,
    )
    from maps.db_functions import SimplifyPreserveTopology

    logger.info("Starting Collection GeoJSON cache warm-up")

    try:
        # Get published collections with optimized query and simplified geometry
        qs = (
            Collection.objects.filter(publication_status="published")
            .select_related(
                "catchment",
                "catchment__region",
                "catchment__region__borders",
                "waste_stream",
                "waste_stream__category",
                "collection_system",
            )
            .annotate(
                simplified_geom=SimplifyPreserveTopology(
                    F("catchment__region__borders__geom"),
                    GEOMETRY_SIMPLIFY_TOLERANCE,
                )
            )
        )

        # Serialize the data with simplified geometry
        serializer = WasteCollectionGeometrySerializer(qs, many=True)
        data = serializer.data

        # Use shared utility for cache key to ensure consistency with viewset
        from maps.utils import build_collection_cache_key

        cache_key = build_collection_cache_key(scope="published")

        # Store in cache
        cache = get_geojson_cache()
        timeout = getattr(settings, "GEOJSON_CACHE_TIMEOUT", 86400)  # 24 hours
        cache.set(cache_key, data, timeout=timeout)

        logger.info(
            "Collection GeoJSON cache warmed: %d features, key=%s",
            len(data.get("features", [])) if isinstance(data, dict) else len(data),
            cache_key,
        )
        return {
            "status": "success",
            "features_count": len(data.get("features", []))
            if isinstance(data, dict)
            else len(data),
            "cache_key": cache_key,
        }

    except Exception as e:
        logger.exception("Failed to warm Collection GeoJSON cache: %s", e)
        return {"status": "error", "error": str(e)}


@shared_task(bind=True, name="warm_roadside_tree_geojson_cache")
def warm_roadside_tree_geojson_cache(self):
    """
    Pre-warm the Hamburg Roadside Trees GeoJSON cache.

    This task should be triggered after tree data imports to ensure
    the cache is populated before users request the data. This prevents
    H12 timeout errors on first requests with ~250k tree points.
    """
    from case_studies.flexibi_hamburg.models import HamburgRoadsideTrees
    from case_studies.flexibi_hamburg.serializers import (
        HamburgRoadsideTreeGeometrySerializer,
    )

    logger.info("Starting Roadside Trees GeoJSON cache warm-up")

    try:
        # Get all trees with optimized query (only id and geom, no ordering)
        qs = HamburgRoadsideTrees.objects.only("id", "geom").order_by()

        # Serialize the data
        serializer = HamburgRoadsideTreeGeometrySerializer(qs, many=True)
        data = serializer.data

        # Cache key must match viewset's get_cache_key() for unfiltered requests
        cache_key = "tree_geojson:all"

        # Store in cache
        cache = get_geojson_cache()
        timeout = getattr(settings, "GEOJSON_CACHE_TIMEOUT", 86400)  # 24 hours
        cache.set(cache_key, data, timeout=timeout)

        feature_count = (
            len(data.get("features", [])) if isinstance(data, dict) else len(data)
        )
        logger.info(
            "Roadside Trees GeoJSON cache warmed: %d features, key=%s",
            feature_count,
            cache_key,
        )
        return {
            "status": "success",
            "features_count": feature_count,
            "cache_key": cache_key,
        }

    except Exception as e:
        logger.exception("Failed to warm Roadside Trees GeoJSON cache: %s", e)
        return {"status": "error", "error": str(e)}


@shared_task(bind=True, name="warm_all_geojson_caches")
def warm_all_geojson_caches(self):
    """
    Warm all GeoJSON caches. Called periodically or after major data changes.
    """
    results = {}

    # Warm Collection cache
    try:
        result = warm_collection_geojson_cache.apply()
        results["collection"] = result.get()
    except Exception as e:
        logger.exception("Failed to warm collection cache: %s", e)
        results["collection"] = {"status": "error", "error": str(e)}

    # Warm Roadside Trees cache
    try:
        result = warm_roadside_tree_geojson_cache.apply()
        results["roadside_trees"] = result.get()
    except Exception as e:
        logger.exception("Failed to warm roadside trees cache: %s", e)
        results["roadside_trees"] = {"status": "error", "error": str(e)}

    return results
