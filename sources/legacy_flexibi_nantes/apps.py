from django.apps import AppConfig


class LegacyFlexibiNantesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.legacy_flexibi_nantes"
    label = "flexibi_nantes"
    verbose_name = "Legacy Nantes Migration Shim"
