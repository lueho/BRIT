import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from maps.signals import clear_geojson_cache_pattern

from .models import Collection

logger = logging.getLogger(__name__)


# Fields that don't affect GeoJSON representation and can skip cache invalidation.
# Includes audit fields that are auto-updated by the base model.
_NON_GEOJSON_FIELDS = frozenset(
    {
        "name",
        "valid_until",
        "lastmodified_at",
        "lastmodified_by",
        "created_at",
        "created_by",
    }
)


@receiver(post_save, sender=Collection)
@receiver(post_delete, sender=Collection)
def invalidate_collection_geojson_cache(sender, instance, **kwargs):
    """
    Proactively clear Soilcom Collection GeoJSON cache whenever a Collection changes.

    This prevents accumulation of outdated dv-based cache entries when data changes frequently.
    Uses Redis delete_pattern via maps.signals.clear_geojson_cache_pattern.

    Skips cache invalidation for updates that only affect non-GeoJSON fields (e.g., name).
    """
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields) <= _NON_GEOJSON_FIELDS:
        logger.debug(
            "Skipping cache invalidation for Collection id=%s (non-GeoJSON update: %s)",
            getattr(instance, "id", None),
            update_fields,
        )
        return

    try:
        clear_geojson_cache_pattern("collection_geojson:*")
        logger.info(
            "Cleared collection_geojson cache after change to Collection id=%s",
            getattr(instance, "id", None),
        )
    except Exception:
        logger.exception(
            "Failed to clear collection_geojson cache on Collection change"
        )
