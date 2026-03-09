from django.apps import AppConfig

class WasteCollectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.waste_collection"
    verbose_name = "Sources / Waste Collection"

    def ready(self):
        signal_module = None
        try:
            from . import signals as signal_module
        except Exception:
            pass

        if signal_module is None:
            return
        try:
            from django.db.models.signals import post_delete, post_save

            CollectionPropertyValue = self.get_model("CollectionPropertyValue")
            post_save.connect(
                signal_module.sync_derived_cpv_on_save,
                sender=CollectionPropertyValue,
                dispatch_uid="waste_collection.sync_derived_cpv_on_save",
            )
            post_delete.connect(
                signal_module.sync_derived_cpv_on_delete,
                sender=CollectionPropertyValue,
                dispatch_uid="waste_collection.sync_derived_cpv_on_delete",
            )
        except LookupError:
            pass
