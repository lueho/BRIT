"""Database-backed registry of Waste Atlas choropleth configurations."""

from collections.abc import Mapping

NO_DATA_COLOR = "#e0e0e0"
BIOWASTE_NO_COLLECTION_COLOR = "#fff696"


class DatabaseMapConfigurations(Mapping):
    """Expose stored configurations through the former mapping interface."""

    @staticmethod
    def _model():
        from .models import WasteAtlasMapConfiguration

        return WasteAtlasMapConfiguration

    def __getitem__(self, key):
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
