import logging

from django.conf import settings

from brit.celery import app
from maps.signals import get_geojson_cache
from sources.roadside_trees.geojson import (
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTrees,
)

logger = logging.getLogger(__name__)


@app.task(bind=True, name="warm_roadside_tree_geojson_cache")
def warm_roadside_tree_geojson_cache(self):
    logger.info("Starting Roadside Trees GeoJSON cache warm-up")

    try:
        qs = HamburgRoadsideTrees.objects.only("id", "geom").order_by()
        serializer = HamburgRoadsideTreeGeometrySerializer(qs, many=True)
        data = serializer.data
        cache_key = "tree_geojson:all"
        cache = get_geojson_cache()
        timeout = getattr(settings, "GEOJSON_CACHE_TIMEOUT", 86400)
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
