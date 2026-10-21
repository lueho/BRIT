from django.apps import AppConfig


class MaterialsConfig(AppConfig):
    name = "materials"

    def ready(self):
        import materials.exports  # noqa: F401
        from brit.sitemap_registry import register_sitemap_items
        from materials.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
