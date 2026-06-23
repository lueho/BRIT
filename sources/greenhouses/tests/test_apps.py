from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from sources.greenhouses.apps import GreenhousesConfig


class GreenhousesConfigReadyTests(SimpleTestCase):
    def setUp(self):
        app_module = import_module("sources.greenhouses")
        self.app_config = GreenhousesConfig("sources.greenhouses", app_module)

    def test_ready_registers_exports(self):
        exports = SimpleNamespace(register_exports=Mock())

        with patch(
            "sources.greenhouses.apps.import_module",
            return_value=exports,
        ) as import_module_mock:
            self.app_config.ready()

        import_module_mock.assert_called_once_with("sources.greenhouses.exports")
        exports.register_exports.assert_called_once_with()
