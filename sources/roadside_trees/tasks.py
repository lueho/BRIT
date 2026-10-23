import logging

from django.conf import settings

from brit.celery import app
from maps.signals import get_geojson_cache
from maps.utils import cache_rendered_geojson, rendered_geojson_cache_key
from sources.roadside_trees.geojson import (
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTrees,
)
from sources.roadside_trees.viewsets import HamburgRoadsideTreeViewSet

logger = logging.getLogger(__name__)

# The production table has over 230,000 rows. Materializing all serialized
# features in a Basic worker exceeds its 512 MB quota and kills the process.
MAX_AUTO_WARMUP_FEATURES = 50_000


@app.task(bind=True, name="warm_roadside_tree_geojson_cache")
def warm_roadside_tree_geojson_cache(self):
    logger.info("Starting Roadside Trees GeoJSON cache warm-up")

    try:
        # Capture the dataset version before serializing: if the externally
        # managed table changes mid-task, the worst case is a fresh payload
        # under an orphaned old key, never stale geometry under a current key.
        stats = HamburgRoadsideTreeViewSet().get_dataset_stats(None)
        if stats["count"] > MAX_AUTO_WARMUP_FEATURES:
            logger.warning(
                "Skipped Roadside Trees GeoJSON warmup: %d features exceed %d",
                stats["count"],
                MAX_AUTO_WARMUP_FEATURES,
            )
            return {"status": "skipped", "features_count": stats["count"]}
        dataset_version = stats["version"]
        qs = HamburgRoadsideTrees.objects.only("id", "geom").order_by()
        base_key = f"tree_geojson:all:dv:{dataset_version}"
        cache_key = rendered_geojson_cache_key(base_key, dataset_version)
        cache = get_geojson_cache()
        timeout = getattr(settings, "GEOJSON_CACHE_TIMEOUT", 86400)
        cached = cache.has_key(cache_key)
        warmed = cached or cache_rendered_geojson(
            cache,
            cache_key,
            qs,
            HamburgRoadsideTreeGeometrySerializer,
            "geom",
            timeout=timeout,
        )
        # The viewset reads only the rendered key now; drop any legacy
        # serializer-payload entry stored under the same version.
        cache.delete(base_key)
        cache.delete(f"{base_key}:count")

        feature_count = 0 if cached else stats["count"] or 0
        logger.info(
            "Roadside Trees GeoJSON cache warmed: %d features, key=%s",
            feature_count,
            cache_key,
        )
        return {
            "status": "success" if warmed else "skipped",
            "features_count": feature_count,
            "cache_key": cache_key,
        }
    except Exception as e:
        logger.exception("Failed to warm Roadside Trees GeoJSON cache: %s", e)
        return {"status": "error", "error": str(e)}
