from django.apps import AppConfig


class ClosecycleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "case_studies.closecycle"

    def ready(self):
        from brit.sitemap_registry import register_sitemap_items
        from case_studies.closecycle.sitemap import SITEMAP_ITEMS

        register_sitemap_items(SITEMAP_ITEMS)
