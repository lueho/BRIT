from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from sources.waste_collection.apps import WasteCollectionConfig


class WasteCollectionConfigReadyTests(SimpleTestCase):
    def setUp(self):
        app_module = import_module("sources.waste_collection")
        self.app_config = WasteCollectionConfig("sources.waste_collection", app_module)

    def test_ready_logs_and_returns_when_signal_import_fails(self):
        with (
            patch(
                "sources.waste_collection.apps.import_module",
                side_effect=RuntimeError("boom"),
            ),
            patch("sources.waste_collection.apps.logger") as logger,
        ):
            self.app_config.ready()

        logger.exception.assert_called_once_with(
            "Failed to import waste_collection signal handlers."
        )

    def test_ready_connects_collection_property_value_signal_handlers(self):
        signal_module = SimpleNamespace(
            sync_derived_cpv_on_save=object(),
            sync_derived_cpv_on_delete=object(),
        )
        collection_property_value_model = object()

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                return_value=signal_module,
            ),
            patch.object(
                self.app_config,
                "get_model",
                return_value=collection_property_value_model,
            ),
            patch("django.db.models.signals.post_save.connect") as post_save_connect,
            patch("django.db.models.signals.post_delete.connect") as post_delete_connect,
        ):
            self.app_config.ready()

        post_save_connect.assert_called_once_with(
            signal_module.sync_derived_cpv_on_save,
            sender=collection_property_value_model,
            dispatch_uid="waste_collection.sync_derived_cpv_on_save",
        )
        post_delete_connect.assert_called_once_with(
            signal_module.sync_derived_cpv_on_delete,
            sender=collection_property_value_model,
            dispatch_uid="waste_collection.sync_derived_cpv_on_delete",
        )

    def test_ready_logs_lookup_errors_when_model_resolution_fails(self):
        signal_module = SimpleNamespace(
            sync_derived_cpv_on_save=object(),
            sync_derived_cpv_on_delete=object(),
        )

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                return_value=signal_module,
            ),
            patch.object(
                self.app_config,
                "get_model",
                side_effect=LookupError("missing model"),
            ),
            patch("sources.waste_collection.apps.logger") as logger,
        ):
            self.app_config.ready()

        logger.warning.assert_called_once_with(
            "Waste collection signal registration skipped because CollectionPropertyValue could not be resolved."
        )
