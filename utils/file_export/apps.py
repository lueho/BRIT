from django.apps import AppConfig


class FileExportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utils.file_export'

    def ready(self):
        # Ensure export registry is initialized in every process (web, celery, management commands)
        # This imports utils.file_export.registry_init which performs registrations via register_export()
        # Safe to import multiple times; registrations simply overwrite the same keys.
        from . import registry_init  # noqa: F401