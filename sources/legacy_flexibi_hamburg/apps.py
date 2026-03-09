from django.apps import AppConfig


class LegacyFlexibiHamburgMigrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.legacy_flexibi_hamburg"
    label = "flexibi_hamburg"
    verbose_name = "Legacy Hamburg Migration Shim"
