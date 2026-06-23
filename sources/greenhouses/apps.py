from importlib import import_module

from django.apps import AppConfig


class GreenhousesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.greenhouses"
    verbose_name = "Sources / Greenhouses"

    def ready(self):
        exports = import_module("sources.greenhouses.exports")
        exports.register_exports()
