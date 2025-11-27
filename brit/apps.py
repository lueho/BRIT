from django.apps import AppConfig


class BRITConfig(AppConfig):
    name = "brit"

    def ready(self):
        # Signals are connected here
        pass
