from django.apps import AppConfig


class SourcesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from sources.registry import initialize_source_domain_registry
        from sources.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
        initialize_source_domain_registry()
