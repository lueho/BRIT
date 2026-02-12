from django.apps import AppConfig


class WasteAtlasConfig(AppConfig):
    """Configuration for the waste atlas submodule."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "case_studies.soilcom.waste_atlas"
    label = "waste_atlas"
    verbose_name = "Waste Atlas"
