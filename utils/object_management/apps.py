from django.apps import AppConfig


class ObjectManagementConfig(AppConfig):
    name = "utils.object_management"
    verbose_name = "Object Management"

    def ready(self):
        # Register signals (safe import; don't crash app startup on errors)
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid failing hard during app loading; issues will surface in logs when signals run
            pass
