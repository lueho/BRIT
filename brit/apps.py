from django.apps import AppConfig


class BRITConfig(AppConfig):
    name = "brit"

    def ready(self):
        from brit.sitemap import SITEMAP_ITEMS
        from brit.sitemap_registry import register_sitemap_items

        register_sitemap_items(SITEMAP_ITEMS)
