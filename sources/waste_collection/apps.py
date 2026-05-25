import logging
from importlib import import_module

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class WasteCollectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sources.waste_collection"
    verbose_name = "Sources / Waste Collection"

    def ready(self):
        try:
            import_module("sources.waste_collection.patches.disable_research_metrics")
        except Exception:
            pass

        try:
            signal_module = import_module("sources.waste_collection.signals")
        except Exception:
            logger.exception("Failed to import waste_collection signal handlers.")
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
            logger.warning(
                "Waste collection signal registration skipped because CollectionPropertyValue could not be resolved."
            )
