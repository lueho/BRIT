from django.apps import AppConfig
from django.core.management import call_command


class BRITConfig(AppConfig):
    name = "brit"

    def ready(self):
        # Signals are connected here
        from .signals import populate_initial_data
