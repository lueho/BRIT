from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from sources.waste_collection.apps import WasteCollectionConfig


class WasteCollectionConfigReadyTests(SimpleTestCase):
    def setUp(self):
        app_module = import_module("sources.waste_collection")
        self.app_config = WasteCollectionConfig("sources.waste_collection", app_module)

    def test_ready_logs_and_returns_when_signal_import_fails(self):
        review_hooks = SimpleNamespace(register_review_hooks=Mock())
        exports = SimpleNamespace(register_exports=Mock())

        def import_side_effect(module_name):
            if module_name == "sources.waste_collection.signals":
                raise RuntimeError("boom")
            if module_name == "sources.waste_collection.review_hooks":
                return review_hooks
            if module_name == "sources.waste_collection.exports":
                return exports
            return SimpleNamespace()

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                side_effect=import_side_effect,
            ),
            patch("sources.waste_collection.apps.logger") as logger,
        ):
            self.app_config.ready()

        logger.exception.assert_called_once_with(
            "Failed to import waste_collection signal handlers."
        )
        exports.register_exports.assert_called_once_with()
        review_hooks.register_review_hooks.assert_called_once_with()

    def test_ready_connects_collection_property_value_signal_handlers(self):
        signal_module = SimpleNamespace(
            sync_derived_cpv_on_save=object(),
            sync_derived_cpv_on_delete=object(),
        )
        review_hooks = SimpleNamespace(register_review_hooks=Mock())
        exports = SimpleNamespace(register_exports=Mock())
        collection_property_value_model = object()

        def import_side_effect(module_name):
            if module_name == "sources.waste_collection.signals":
                return signal_module
            if module_name == "sources.waste_collection.review_hooks":
                return review_hooks
            if module_name == "sources.waste_collection.exports":
                return exports
            return SimpleNamespace()

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                side_effect=import_side_effect,
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

        review_hooks.register_review_hooks.assert_called_once_with()
        exports.register_exports.assert_called_once_with()
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
        review_hooks = SimpleNamespace(register_review_hooks=Mock())
        exports = SimpleNamespace(register_exports=Mock())

        def import_side_effect(module_name):
            if module_name == "sources.waste_collection.signals":
                return signal_module
            if module_name == "sources.waste_collection.review_hooks":
                return review_hooks
            if module_name == "sources.waste_collection.exports":
                return exports
            return SimpleNamespace()

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                side_effect=import_side_effect,
            ),
            patch.object(
                self.app_config,
                "get_model",
                side_effect=LookupError("missing model"),
            ),
            patch("sources.waste_collection.apps.logger") as logger,
        ):
            self.app_config.ready()

        review_hooks.register_review_hooks.assert_called_once_with()
        exports.register_exports.assert_called_once_with()
        logger.warning.assert_called_once_with(
            "Waste collection signal registration skipped because CollectionPropertyValue could not be resolved."
        )

    def test_ready_imports_research_metrics_patch(self):
        review_hooks = SimpleNamespace(register_review_hooks=Mock())
        exports = SimpleNamespace(register_exports=Mock())
        signal_module = SimpleNamespace(
            sync_derived_cpv_on_save=object(),
            sync_derived_cpv_on_delete=object(),
        )

        def import_side_effect(module_name):
            if module_name == "sources.waste_collection.signals":
                return signal_module
            if module_name == "sources.waste_collection.review_hooks":
                return review_hooks
            if module_name == "sources.waste_collection.exports":
                return exports
            return SimpleNamespace()

        with (
            patch(
                "sources.waste_collection.apps.import_module",
                side_effect=import_side_effect,
            ) as import_module_mock,
            patch.object(self.app_config, "get_model", return_value=object()),
            patch("django.db.models.signals.post_save.connect"),
            patch("django.db.models.signals.post_delete.connect"),
        ):
            self.app_config.ready()

        imported_modules = [call.args[0] for call in import_module_mock.call_args_list]
        self.assertIn(
            "sources.waste_collection.patches.disable_research_metrics",
            imported_modules,
        )
        self.assertIn("sources.waste_collection.exports", imported_modules)
        self.assertIn("sources.waste_collection.review_hooks", imported_modules)
        exports.register_exports.assert_called_once_with()
