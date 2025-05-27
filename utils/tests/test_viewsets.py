from unittest.mock import MagicMock, patch

from django.test import TestCase

from utils.viewsets import AutoPermModelViewSet


class AutoPermModelViewSetTests(TestCase):
    def setUp(self):
        self.viewset = AutoPermModelViewSet()
        model = MagicMock()
        model._meta.model_name = "testmodel"
        model._meta.app_label = "testapp"
        self.viewset.get_queryset = MagicMock(return_value=MagicMock(model=model))

    def test_generate_permission_required(self):
        expected = {
            "create": "testapp.add_testmodel",
            "list": "testapp.view_testmodel",
            "retrieve": "testapp.view_testmodel",
            "update": "testapp.change_testmodel",
            "partial_update": "testapp.change_testmodel",
            "destroy": "testapp.delete_testmodel",
        }
        self.assertEqual(self.viewset._generate_permission_required(), expected)

    def test_custom_permission_override(self):
        self.viewset.custom_permission_required = {"list": "custom.list"}
        self.assertEqual(self.viewset.permission_required["list"], "custom.list")

    def test_permission_required_cached(self):
        with patch.object(
            self.viewset,
            "_generate_permission_required",
            wraps=self.viewset._generate_permission_required,
        ) as mocked:
            _ = self.viewset.permission_required
            _ = self.viewset.permission_required
            mocked.assert_called_once()

    def test_get_permissions_triggers_generation(self):
        self.assertFalse(self.viewset._permission_required_generated)
        self.viewset.get_permissions()
        self.assertTrue(self.viewset._permission_required_generated)
