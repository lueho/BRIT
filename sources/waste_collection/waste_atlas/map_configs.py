"""Database-backed registry of Waste Atlas choropleth configurations."""

from collections.abc import Mapping

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .caching import delete_scoped, scoped_cache_key


def no_data_color():
    """Return the configured fill for regions without data."""
    from .models import WasteAtlasRenderingSettings

    return WasteAtlasRenderingSettings.load().no_data_color


def no_collection_color():
    """Return the configured fill for regions without separate collection."""
    from .models import WasteAtlasRenderingSettings

    return WasteAtlasRenderingSettings.load().no_collection_color


class DatabaseMapConfigurations(Mapping):
    """Expose stored configurations through the former mapping interface.

    ``__getitem__`` runs on every map render, so lookups are cached in the
    default cache and invalidated by the ``WasteAtlasMapConfiguration``
    ``post_save``/``post_delete`` receivers below. Keys are scoped to the
    current transaction (see ``caching.scoped_cache_key``), so values written
    inside a rolled-back block cannot leak. The pickle boundary gives every
    caller an independent copy, matching the previous per-query JSON
    deserialization.
    """

    _CACHE_KEY_PREFIX = "waste_atlas:map_configuration:"

    @staticmethod
    def _model():
        from .models import WasteAtlasMapConfiguration

        return WasteAtlasMapConfiguration

    @classmethod
    def _cache_key(cls, key):
        return f"{cls._CACHE_KEY_PREFIX}{key}"

    def __getitem__(self, key):
        cache_key = scoped_cache_key(self._cache_key(key))
        configuration = cache.get(cache_key)
        if configuration is None:
            try:
                configuration = (
                    self._model()
                    .objects.values_list(
                        "configuration",
                        flat=True,
                    )
                    .get(key=key)
                )
            except self._model().DoesNotExist as exc:
                raise KeyError(key) from exc
            cache.set(cache_key, configuration)
        return dict(configuration)

    def __iter__(self):
        return iter(self._model().objects.values_list("key", flat=True))

    def __len__(self):
        return self._model().objects.count()

    def items(self):
        return (
            (key, dict(configuration))
            for key, configuration in self._model()
            .objects.values_list("key", "configuration")
            .iterator()
        )

    def values(self):
        return (
            dict(configuration)
            for configuration in self._model()
            .objects.values_list("configuration", flat=True)
            .iterator()
        )


MAP_CONFIGS = DatabaseMapConfigurations()


@receiver(post_save, sender="waste_atlas.WasteAtlasMapConfiguration")
@receiver(post_delete, sender="waste_atlas.WasteAtlasMapConfiguration")
def invalidate_map_configuration_cache(sender, instance, **kwargs):
    delete_scoped(cache, MAP_CONFIGS._cache_key(instance.key))
