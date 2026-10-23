from django.apps import AppConfig


class InventoriesConfig(AppConfig):
    name = "inventories"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from inventories.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
