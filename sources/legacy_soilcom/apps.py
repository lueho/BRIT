from django.apps import AppConfig


class LegacySoilcomConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.legacy_soilcom"
    label = "soilcom"
    verbose_name = "Legacy Soilcom Migration Shim"
