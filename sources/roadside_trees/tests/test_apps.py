from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from sources.roadside_trees.apps import RoadsideTreesConfig


class RoadsideTreesConfigReadyTests(SimpleTestCase):
    def setUp(self):
        app_module = import_module("sources.roadside_trees")
        self.app_config = RoadsideTreesConfig("sources.roadside_trees", app_module)

    def test_ready_registers_exports(self):
        exports = SimpleNamespace(register_exports=Mock())

        with patch(
            "sources.roadside_trees.apps.import_module",
            return_value=exports,
        ) as import_module_mock:
            self.app_config.ready()

        import_module_mock.assert_called_once_with("sources.roadside_trees.exports")
        exports.register_exports.assert_called_once_with()
