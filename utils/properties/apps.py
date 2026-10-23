from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utils.properties"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from utils.properties.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
