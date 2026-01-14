import logging

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Catchment, GeoPolygon, LauRegion, NutsRegion, Region

logger = logging.getLogger(__name__)


def get_geojson_cache():
    """
    Retrieve the cache instance using the GEOJSON_CACHE setting.
    Defaults to the 'default' cache if GEOJSON_CACHE is not specified.
    """
    cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
    return caches[cache_alias]


def clear_geojson_cache_pattern(pattern: str) -> None:
    """
    Clear cache keys matching the given pattern using the backend's delete_pattern.

    This function assumes the cache backend (e.g. django-redis) supports
    delete_pattern. If not, it logs an error and raises ImproperlyConfigured.
    """
    geojson_cache = get_geojson_cache()
    try:
        delete_pattern = getattr(geojson_cache, "delete_pattern", None)
        if callable(delete_pattern):
            deleted_count = delete_pattern(pattern)
            logger.info(
                f"Cleared {deleted_count} cache keys matching pattern: {pattern}"
            )
        else:
            msg = (
                f"Cache backend '{geojson_cache.__class__.__name__}' does not support 'delete_pattern'. "
                f"Cannot clear pattern: {pattern}. Please use a compatible Redis cache backend."
            )
            logger.error(msg)
            raise ImproperlyConfigured(msg)
    except Exception as e:
        logger.exception(f"Error clearing cache pattern '{pattern}': {e}")


def safe_cache_delete(cache, key: str) -> None:
    """
    Delete a single cache key and log any exceptions.
    """
    try:
        cache.delete(key)
        logger.debug(f"Deleted cache key: {key}")
    except Exception as e:
        logger.exception(f"Error deleting cache key '{key}': {e}")


@receiver(post_save, sender=Region)
@receiver(post_delete, sender=Region)
def invalidate_region_cache(sender, instance, **kwargs):
    """
    Invalidate region cache when a Region instance is saved or deleted.
    Clears both the specific region cache and any broad region filters.
    """
    geojson_cache = get_geojson_cache()
    safe_cache_delete(geojson_cache, f"region_geojson:id:{instance.id}")

    # Broad invalidation for any keys using the region namespace.
    clear_geojson_cache_pattern("region_geojson:*")

    # Catchment geometries depend on the underlying region geometries.
    clear_geojson_cache_pattern("catchment_geojson:*")

    # Invalidate NUTS cache if the region has an associated NUTS region.
    if hasattr(instance, "nutsregion"):
        clear_geojson_cache_pattern("nuts_geojson:*")


@receiver(post_save, sender=GeoPolygon)
def invalidate_related_region_caches_for_geopolygon(sender, instance, **kwargs):
    """Invalidate dependent caches when a GeoPolygon geometry changes.

    Regions expose their geometry via the related GeoPolygon (Region.borders).
    A GeoPolygon save does not necessarily trigger a Region save, so we bump the
    related Region(s) lastmodified timestamp to ensure dataset versions change.
    """

    now = timezone.now()
    updated = Region.objects.filter(borders_id=instance.pk).update(lastmodified_at=now)
    if not updated:
        return

    # Ensure any existing cached geojson responses are invalidated.
    clear_geojson_cache_pattern("region_geojson:*")
    clear_geojson_cache_pattern("catchment_geojson:*")
    clear_geojson_cache_pattern("nuts_geojson:*")
    clear_geojson_cache_pattern("lau_geojson:*")


@receiver(post_save, sender=Catchment)
@receiver(post_delete, sender=Catchment)
def invalidate_catchment_cache(sender, instance, **kwargs):
    """
    Invalidate catchment cache when a Catchment instance is saved or deleted.
    """
    geojson_cache = get_geojson_cache()
    safe_cache_delete(geojson_cache, f"catchment_geojson:id:{instance.id}")
    clear_geojson_cache_pattern("catchment_geojson:*")


@receiver(post_save, sender=NutsRegion)
@receiver(post_delete, sender=NutsRegion)
def invalidate_nuts_region_cache(sender, instance, **kwargs):
    """
    Invalidate NUTS region cache when a NutsRegion instance is saved or deleted.
    """
    geojson_cache = get_geojson_cache()
    safe_cache_delete(geojson_cache, f"nuts_geojson:id:{instance.id}")
    clear_geojson_cache_pattern("nuts_geojson:*")

    # Invalidate caches for any parent relationships.
    if instance.parent_id:
        clear_geojson_cache_pattern(f"nuts_geojson:parent:{instance.parent_id}:*")


@receiver(post_save, sender=LauRegion)
@receiver(post_delete, sender=LauRegion)
def invalidate_lau_region_cache(sender, instance, **kwargs):
    """
    Invalidate LAU region cache when a LauRegion instance is saved or deleted.

    For LAU regions, this example assumes separate cache keys (e.g., 'lau_geojson:*').
    Adjust the key patterns if LAU regions should also trigger invalidation of related NUTS caches.
    """
    # Invalidate the LAU-specific cache keys.
    clear_geojson_cache_pattern("lau_geojson:*")

    # If a LAU region is linked to a parent NUTS region, invalidate its caches as well.
    if hasattr(instance, "nuts_parent") and instance.nuts_parent:
        clear_geojson_cache_pattern(f"nuts_geojson:id:{instance.nuts_parent.id}")
        clear_geojson_cache_pattern(f"nuts_geojson:parent:{instance.nuts_parent.id}:*")
