import logging
from datetime import timedelta
from types import SimpleNamespace

from celery import chord
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone

from bibliography.utils import check_url
from brit.celery import app
from maps.db_functions import SimplifyPreserveTopology
from maps.signals import get_geojson_cache
from maps.utils import (
    AUTHZ_GEOJSON_CACHE_PREFIX,
    build_collection_cache_key,
    cache_rendered_geojson,
    rendered_geojson_cache_key,
)
from sources.waste_collection.filters import WasteFlyerFilter
from sources.waste_collection.geojson import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    Collection,
    WasteCollectionGeometrySerializer,
    exclude_published_predecessors,
)
from sources.waste_collection.models import WasteFlyer
from utils.object_management.permissions import filter_queryset_for_user
from utils.object_management.policy import decide

logger = logging.getLogger(__name__)


@app.task(bind=True, name="warm_collection_geojson_cache")
def warm_collection_geojson_cache(self):
    qs = (
        exclude_published_predecessors(
            Collection.objects.filter(publication_status="published")
        )
        .select_related(
            "catchment",
            "catchment__region",
            "catchment__region__borders",
            "waste_category",
            "collection_system",
        )
        .annotate(
            simplified_geom=SimplifyPreserveTopology(
                F("catchment__region__borders__geom"),
                GEOMETRY_SIMPLIFY_TOLERANCE,
            )
        )
    )

    logger.info("Starting Collection GeoJSON cache warm-up")

    try:
        # Compute the versioned key before serializing: a write landing
        # mid-task then produces a fresh payload under an orphaned old key,
        # never stale geometry under a current key.
        from sources.waste_collection.viewsets import CollectionViewSet

        # Anonymous requests read the ``authz-v1:`` namespace exclusively, so
        # warm the namespaced key that public-historical lookups resolve.
        base_key = f"{AUTHZ_GEOJSON_CACHE_PREFIX}{build_collection_cache_key(scope='published')}"
        view = CollectionViewSet()
        aggregates = qs.aggregate(**view._version_aggregates())
        cache_key = rendered_geojson_cache_key(
            base_key, view._version_token(aggregates)
        )
        cache = get_geojson_cache()
        timeout = getattr(settings, "GEOJSON_CACHE_TIMEOUT", 86400)
        cached = cache.has_key(cache_key)
        warmed = cached or cache_rendered_geojson(
            cache,
            cache_key,
            qs,
            WasteCollectionGeometrySerializer,
            "simplified_geom",
            timeout=timeout,
            geometry_defer_field="catchment__region__borders__geom",
        )
        cache.delete(base_key)
        cache.delete(f"{base_key}:count")
        feature_count = 0 if cached else aggregates["cnt"] or 0
        logger.info(
            "Collection GeoJSON cache warmed: %d features, key=%s",
            feature_count,
            cache_key,
        )
        return {
            "status": "success" if warmed else "skipped",
            "features_count": feature_count,
            "cache_key": cache_key,
        }
    except Exception as e:
        logger.exception("Failed to warm Collection GeoJSON cache: %s", e)
        return {"status": "error", "error": str(e)}


@app.task(name="check_wasteflyer_url", trail=True)
def check_wasteflyer_url(pk, user_id=None):
    """Refresh only ``url_valid``/``url_checked`` health metadata for a flyer.

    When a ``user_id`` is supplied the acting identity's current
    ``check_url`` decision is re-evaluated before any write.
    """
    flyer = WasteFlyer.objects.filter(pk=pk).first()
    if flyer is None:
        return False

    if user_id is not None:
        actor = get_user_model().objects.filter(pk=user_id).first()
        if actor is None or not decide(actor, "check_url", flyer).allowed:
            return False

    flyer.url_valid = check_url(flyer.url)
    flyer.url_checked = timezone.localdate()
    flyer.save(update_fields=["url_valid", "url_checked"])
    return True


@app.task(name="callback")
def check_wasteflyer_urls_callback(results):
    return f"Checked {len(results)} flyers."


@app.task(bind=True, trail=True, name="scheduler")
def check_wasteflyer_urls(self, params, user_id=None):
    self.myname = "scheduler"
    user = None
    if user_id:
        user = get_user_model().objects.filter(pk=user_id).first()
    request = SimpleNamespace(user=user)

    qs = WasteFlyerFilter(params, queryset=WasteFlyer.objects.all(), request=request).qs
    if user is not None:
        qs = filter_queryset_for_user(qs, user)
    signatures = []
    for flyer in qs:
        if user is None or decide(user, "check_url", flyer).allowed:
            signatures.append(check_wasteflyer_url.s(flyer.pk, user_id))
    callback = check_wasteflyer_urls_callback.s()
    task_chord = chord(signatures)(callback)
    return task_chord.task_id


FLYER_ORPHAN_GRACE_PERIOD = timedelta(days=7)


@app.task(name="cleanup_orphaned_waste_flyers", trail=True)
def cleanup_orphaned_waste_flyers():
    """Delete WasteFlyers that are not referenced anywhere anymore.

    WasteFlyer is a proxy of bibliography.Source, so a flyer can also be cited
    by models outside waste_collection (materials, processes, maps, ...). The
    orphan predicate must cover every Source back-reference: deleting a cited
    flyer would silently drop M2M citations or abort on protected FKs. Flyers
    younger than FLYER_ORPHAN_GRACE_PERIOD are kept so freshly created
    standalone flyers can still be linked before the next cleanup run.
    """

    return WasteFlyer.objects.filter(
        created_at__lt=timezone.now() - FLYER_ORPHAN_GRACE_PERIOD,
        collections__isnull=True,
        collection__isnull=True,
        collectionpropertyvalue__isnull=True,
        aggregatedcollectionpropertyvalue__isnull=True,
        analyticalmethod__isnull=True,
        sample_groups__isnull=True,
        materialpropertyvalue__isnull=True,
        sample__isnull=True,
        componentmeasurement__isnull=True,
        processes__isnull=True,
        process_source_links__isnull=True,
        external_sample_records__isnull=True,
        population_datasets__isnull=True,
        inventoryalgorithm__isnull=True,
        catchmentrevision__isnull=True,
        geodatasets__isnull=True,
    ).delete()


__all__ = [
    "check_wasteflyer_url",
    "check_wasteflyer_urls",
    "check_wasteflyer_urls_callback",
    "cleanup_orphaned_waste_flyers",
    "warm_collection_geojson_cache",
]
