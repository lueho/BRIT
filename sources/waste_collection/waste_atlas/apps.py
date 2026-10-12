from django.apps import AppConfig


class WasteAtlasConfig(AppConfig):
    """Configuration for the waste atlas submodule."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.waste_collection.waste_atlas"
    label = "waste_atlas"
    verbose_name = "Waste Atlas"

    def ready(self):
        # Import so the MAP_CONFIGS cache-invalidation receivers connect.
        from . import map_configs  # noqa: F401
