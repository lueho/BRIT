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
            sync_derived_acpv_on_save=object(),
            sync_derived_acpv_on_delete=object(),
            sync_derived_acpv_on_collections_changed=object(),
        )
        review_hooks = SimpleNamespace(register_review_hooks=Mock())
        exports = SimpleNamespace(register_exports=Mock())
        collection_property_value_model = object()
        aggregated_property_value_model = Mock()
        models_by_name = {
            "CollectionPropertyValue": collection_property_value_model,
            "AggregatedCollectionPropertyValue": aggregated_property_value_model,
        }

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
                side_effect=models_by_name.get,
            ),
            patch("django.db.models.signals.post_save.connect") as post_save_connect,
            patch(
                "django.db.models.signals.post_delete.connect"
            ) as post_delete_connect,
            patch(
                "django.db.models.signals.m2m_changed.connect"
            ) as m2m_changed_connect,
        ):
            self.app_config.ready()

        review_hooks.register_review_hooks.assert_called_once_with()
        exports.register_exports.assert_called_once_with()
        post_save_connect.assert_any_call(
            signal_module.sync_derived_cpv_on_save,
            sender=collection_property_value_model,
            dispatch_uid="waste_collection.sync_derived_cpv_on_save",
        )
        post_save_connect.assert_any_call(
            signal_module.sync_derived_acpv_on_save,
            sender=aggregated_property_value_model,
            dispatch_uid="waste_collection.sync_derived_acpv_on_save",
        )
        post_delete_connect.assert_any_call(
            signal_module.sync_derived_cpv_on_delete,
            sender=collection_property_value_model,
            dispatch_uid="waste_collection.sync_derived_cpv_on_delete",
        )
        post_delete_connect.assert_any_call(
            signal_module.sync_derived_acpv_on_delete,
            sender=aggregated_property_value_model,
            dispatch_uid="waste_collection.sync_derived_acpv_on_delete",
        )
        m2m_changed_connect.assert_called_once_with(
            signal_module.sync_derived_acpv_on_collections_changed,
            sender=aggregated_property_value_model.collections.through,
            dispatch_uid="waste_collection.sync_derived_acpv_on_collections_changed",
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
        logger.warning.assert_any_call(
            "Waste collection signal registration skipped because CollectionPropertyValue could not be resolved."
        )
        logger.warning.assert_any_call(
            "Waste collection signal registration skipped because AggregatedCollectionPropertyValue could not be resolved."
        )
        self.assertEqual(logger.warning.call_count, 2)
