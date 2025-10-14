import logging

from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from maps.signals import clear_geojson_cache_pattern
from .models import Collection

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Collection)
@receiver(post_delete, sender=Collection)
def invalidate_collection_geojson_cache(sender, instance, **kwargs):
    """
    Proactively clear Soilcom Collection GeoJSON cache whenever a Collection changes.

    This prevents accumulation of outdated dv-based cache entries when data changes frequently.
    Uses Redis delete_pattern via maps.signals.clear_geojson_cache_pattern.
    """
    try:
        clear_geojson_cache_pattern("collection_geojson:*")
        logger.info("Cleared collection_geojson cache after change to Collection id=%s", getattr(instance, "id", None))
    except Exception:
        logger.exception("Failed to clear collection_geojson cache on Collection change")
