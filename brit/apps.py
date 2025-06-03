from django.apps import AppConfig
from django.core.management import call_command


class BRITConfig(AppConfig):
    name = "brit"

    def ready(self):
        # Ensure export registry is initialized at startup
        import utils.file_export.registry_init
