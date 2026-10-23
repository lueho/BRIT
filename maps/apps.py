import importlib

from django.apps import AppConfig


class MapsConfig(AppConfig):
    name = "maps"

    def ready(self):
        importlib.import_module("maps.signals")
        from brit.sitemap_registry import register_sitemap_items
        from maps.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
