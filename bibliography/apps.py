from django.apps import AppConfig


class BibliographyConfig(AppConfig):
    name = "bibliography"

    def ready(self):
        from bibliography.sitemap import SITEMAP_ITEMS
        from brit.sitemap_registry import register_sitemap_items

        register_sitemap_items(SITEMAP_ITEMS)
