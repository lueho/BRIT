import importlib

from django.apps import AppConfig


class MapsConfig(AppConfig):
    name = "maps"

    def ready(self):
        importlib.import_module("maps.signals")
