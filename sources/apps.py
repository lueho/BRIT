from django.apps import AppConfig


class SourcesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources"

    def ready(self):
        from sources.registry import initialize_source_domain_registry

        initialize_source_domain_registry()
