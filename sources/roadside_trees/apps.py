from importlib import import_module

from django.apps import AppConfig


class RoadsideTreesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.roadside_trees"
    verbose_name = "Sources / Roadside Trees"

    def ready(self):
        exports = import_module("sources.roadside_trees.exports")
        exports.register_exports()
