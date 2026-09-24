"""Helpers for warming the base GeoJSON caches (NUTS regions and large Regions).

The logic lives here so it can be shared between the ``warm_geojson_cache``
management command (synchronous, operator-driven) and the
``warm_base_geojson_caches`` Celery task (scheduled, deploy-time, async).
"""

import logging

from django.conf import settings
from django.contrib.gis.db.models.functions import NumPoints
from django.core.cache import caches

from maps.models import NutsRegion, NutsVintage, Region
from maps.serializers import (
    NutsRegionGeometrySerializer,
    RegionGeoFeatureModelSerializer,
)
from maps.utils import (
    get_nuts_region_cache_key,
    get_region_cache_key,
    set_geojson_cache_payload,
)

logger = logging.getLogger(__name__)

DEFAULT_NUTS_LEVELS = (0, 1, 2)

# Number of largest regions to warm by default. The H27 "Client Request
# Interrupted" warnings come almost entirely from crawlers fetching the few
# very large overview regions (e.g. "Europe (NUTS)", "Waste Atlas Background"),
# so warming the heaviest geometries covers the expensive cases cheaply.
DEFAULT_REGIONS_LIMIT = 50

# Regions with more points than this are skipped during warmup: serializing
# them materializes the full coordinate tree in the worker process and OOMs a
# Basic (512 MB) dyno — observed R15 at ~1.1 GB on the ~1M-point
# "Waste Atlas Background" region, which then crash-loops the dyno via the
# worker_ready re-warm. Oversized regions stay request-cached instead.
REGION_GEOJSON_WARMUP_MAX_POINTS = 100_000


def warm_nuts_geojson_cache(nuts_levels=None, limit=None):
    """Warm the NUTS region GeoJSON cache.

    Requests are served one vintage at a time, and the keys carry that
    vintage, so warming anything but the vintage on display is a no-op.
    """
    geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
    if nuts_levels is None:
        nuts_levels = DEFAULT_NUTS_LEVELS
    vintage = NutsVintage.default()
    year = vintage.year if vintage else None

    warmed = 0
    for level in nuts_levels:
        queryset = NutsRegion.objects.filter(levl_code=level)
        if vintage:
            queryset = queryset.in_vintage(vintage)
        if limit:
            queryset = queryset[:limit]

        for region in queryset:
            cache_key = get_nuts_region_cache_key(nuts_id=region.id, version=year)
            serializer = NutsRegionGeometrySerializer([region], many=True)
            set_geojson_cache_payload(geojson_cache, cache_key, serializer.data)
            warmed += 1

        # Also cache the per-level collection
        cache_key = get_nuts_region_cache_key(level=level, version=year)
        serializer = NutsRegionGeometrySerializer(queryset, many=True)
        set_geojson_cache_payload(geojson_cache, cache_key, serializer.data)

    logger.info("NUTS GeoJSON cache warmed: %d entries", warmed)
    return {"status": "success", "features_count": warmed}


def warm_region_geojson_cache(limit=None, max_points=None):
    """Warm the Region GeoJSON cache for the largest geometries.

    Region GeoJSON is requested per ``id`` (``region_geojson:id:<id>``), so
    the heavy overview regions are serialized fresh on every cold cache.
    Pre-warming the largest geometries turns those crawler hits into cache
    hits and avoids the multi-second responses that trigger H27 warnings.

    Regions above ``max_points`` vertices are skipped: their serialized
    payload does not fit into the worker's memory quota (see
    ``REGION_GEOJSON_WARMUP_MAX_POINTS``).
    """
    cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
    geojson_cache = caches[cache_alias]
    # Mirror the viewset's cache timeout so warmed entries live exactly as
    # long as ones written by a normal request (default 24h for the geojson
    # cache) instead of relying on the backend's implicit default.
    timeout = settings.CACHES.get(cache_alias, {}).get("TIMEOUT", 3600)
    if limit is None:
        limit = DEFAULT_REGIONS_LIMIT
    if max_points is None:
        max_points = REGION_GEOJSON_WARMUP_MAX_POINTS

    # Decide from the point counts alone which regions to warm: selecting
    # the geometries up front would load every oversized geometry into the
    # worker before it is skipped.
    candidates = (
        Region.objects.filter(borders__isnull=False)
        .annotate(num_points=NumPoints("borders__geom"))
        .order_by("-num_points")
        .values_list("id", "name", "num_points")[:limit]
    )

    eligible_ids = []
    skipped = []
    for region_id, name, num_points in candidates:
        if (num_points or 0) > max_points:
            skipped.append({"id": region_id, "name": name, "num_points": num_points})
        else:
            eligible_ids.append(region_id)

    warmed = 0
    for region_id in eligible_ids:
        region = Region.objects.select_related("borders").get(id=region_id)
        cache_key = get_region_cache_key(region_id=region.id)
        serializer = RegionGeoFeatureModelSerializer([region], many=True)
        set_geojson_cache_payload(
            geojson_cache, cache_key, serializer.data, timeout=timeout
        )
        warmed += 1

    if skipped:
        logger.warning(
            "Skipped %d oversized regions during GeoJSON warmup (>%d points): %s",
            len(skipped),
            max_points,
            skipped,
        )
    logger.info("Region GeoJSON cache warmed: %d entries", warmed)
    return {"status": "success", "features_count": warmed, "skipped": skipped}
