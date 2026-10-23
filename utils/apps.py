from django.apps import AppConfig


class UtilsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utils"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from utils.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
