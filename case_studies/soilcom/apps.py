from django.apps import AppConfig


class SoilcomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'case_studies.soilcom'

    def ready(self):
        # Import signals to ensure receivers are registered
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid crashing app startup if signals import fails; log in signals module instead if needed
            pass
