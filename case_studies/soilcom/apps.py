from django.apps import AppConfig


class SoilcomConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "case_studies.soilcom"

    def ready(self):
        # Import signals to ensure receivers are registered
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid crashing app startup if signals import fails; log in signals module instead if needed
            pass

        # Connect derived-CPV signals lazily to avoid circular imports.
        # The try/except handles isolate_apps() in tests where models
        # may not be registered yet.
        try:
            from django.db.models.signals import post_delete, post_save

            CollectionPropertyValue = self.get_model("CollectionPropertyValue")
            post_save.connect(
                signals.sync_derived_cpv_on_save,
                sender=CollectionPropertyValue,
                dispatch_uid="sync_derived_cpv_on_save",
            )
            post_delete.connect(
                signals.sync_derived_cpv_on_delete,
                sender=CollectionPropertyValue,
                dispatch_uid="sync_derived_cpv_on_delete",
            )
        except LookupError:
            pass
