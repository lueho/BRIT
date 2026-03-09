import logging

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_delete, post_save, pre_save
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


def _schedule_cache_warmup():
    """Schedule cache warmup task after cache invalidation.

    Uses Celery to asynchronously warm the cache so the next request
    doesn't timeout. Only runs if Celery is available.
    """
    # Skip during testing
    if getattr(settings, "TESTING", False):
        return

    cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
    cache = caches[cache_alias]
    debounce_seconds = getattr(settings, "COLLECTION_GEOJSON_WARMUP_DEBOUNCE", 60)
    lock_key = "collection_geojson:warmup:scheduled"
    lock_acquired = True
    if debounce_seconds:
        lock_acquired = cache.add(lock_key, True, timeout=debounce_seconds)
        if not lock_acquired:
            logger.debug("Collection GeoJSON warm-up already scheduled; skipping")
            return

    try:
        from maps.tasks import warm_collection_geojson_cache

        # Delay warmup by 5 seconds to allow any batch updates to complete
        warm_collection_geojson_cache.apply_async(countdown=5)
        logger.debug("Scheduled collection GeoJSON cache warm-up task")
    except ImportError:
        logger.debug("Cache warm-up task not available")
    except Exception as e:
        logger.warning("Failed to schedule cache warm-up task: %s", e)
        if lock_acquired and debounce_seconds:
            cache.delete(lock_key)


def _published_cache_might_change(instance, *, created=False, is_delete=False):
    """Return True when a collection change can affect the published dataset."""
    current_status = getattr(instance, "publication_status", None)
    previous_status = getattr(instance, "_previous_publication_status", None)

    if is_delete:
        return current_status == Collection.STATUS_PUBLISHED
    if created:
        return current_status == Collection.STATUS_PUBLISHED
    return (
        current_status == Collection.STATUS_PUBLISHED
        or previous_status == Collection.STATUS_PUBLISHED
    )


@receiver(pre_save, sender=Collection)
def capture_previous_collection_publication_status(sender, instance, **kwargs):
    """Store previous publication_status so post_save can detect status transitions."""
    if not instance.pk:
        instance._previous_publication_status = None
        return

    update_fields = kwargs.get("update_fields")
    if update_fields and "publication_status" not in update_fields:
        # publication_status cannot change in this save call
        instance._previous_publication_status = instance.publication_status
        return

    instance._previous_publication_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("publication_status", flat=True)
        .first()
    )


@receiver(post_save, sender=Collection)
@receiver(post_delete, sender=Collection)
def invalidate_collection_geojson_cache(sender, instance, **kwargs):
    """
    Proactively clear Soilcom Collection GeoJSON cache whenever a Collection changes.

    This prevents accumulation of outdated dv-based cache entries when data changes frequently.
    Uses Redis delete_pattern via maps.signals.clear_geojson_cache_pattern.

    Skips cache invalidation for updates that only affect non-GeoJSON fields (e.g., name).
    After invalidation, schedules a cache warm-up task to prevent H12 timeouts.
    """
    is_delete = "created" not in kwargs
    created = kwargs.get("created", False)

    if not is_delete:
        update_fields = kwargs.get("update_fields")
        if update_fields and set(update_fields) <= _NON_GEOJSON_FIELDS:
            logger.debug(
                "Skipping cache invalidation for Collection id=%s (non-GeoJSON update: %s)",
                getattr(instance, "id", None),
                update_fields,
            )
            return

    if not _published_cache_might_change(
        instance, created=created, is_delete=is_delete
    ):
        logger.debug(
            "Skipping published cache invalidation for Collection id=%s (status=%s, previous=%s)",
            getattr(instance, "id", None),
            getattr(instance, "publication_status", None),
            getattr(instance, "_previous_publication_status", None),
        )
        return

    try:
        clear_geojson_cache_pattern("collection_geojson:*")
        logger.info(
            "Cleared collection_geojson cache after change to Collection id=%s",
            getattr(instance, "id", None),
        )
        # Schedule cache warm-up to prevent timeout on next request
        _schedule_cache_warmup()
    except Exception:
        logger.exception(
            "Failed to clear collection_geojson cache on Collection change"
        )


# ---------------------------------------------------------------------------
# Derived CollectionPropertyValue (specific ↔ total waste collected)
# ---------------------------------------------------------------------------


def sync_derived_cpv_on_save(sender, instance, **kwargs):
    """Create or update the derived counterpart when a source CPV is saved."""
    try:
        from .derived_values import (
            create_or_update_derived_cpv,
            is_convertible_property,
        )

        if instance.is_derived:
            return
        if not is_convertible_property(instance.property_id):
            return

        create_or_update_derived_cpv(instance)
    except ImproperlyConfigured as exc:
        logger.debug(
            "Skipping derived CPV sync for CollectionPropertyValue id=%s: %s",
            instance.pk,
            exc,
        )
    except Exception:
        logger.exception(
            "Failed to sync derived CPV for CollectionPropertyValue id=%s",
            instance.pk,
        )


def sync_derived_cpv_on_delete(sender, instance, **kwargs):
    """Delete derived counterparts when a source CPV is deleted."""
    try:
        from .derived_values import delete_derived_cpv, is_convertible_property

        if instance.is_derived:
            return
        if not is_convertible_property(instance.property_id):
            return

        delete_derived_cpv(instance)
    except ImproperlyConfigured as exc:
        logger.debug(
            "Skipping derived CPV delete sync for CollectionPropertyValue id=%s: %s",
            instance.pk,
            exc,
        )
    except Exception:
        logger.exception(
            "Failed to delete derived CPV for CollectionPropertyValue id=%s",
            instance.pk,
        )
