from django.apps import AppConfig


class SimucfConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "interfaces.simucf"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from interfaces.simucf.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
