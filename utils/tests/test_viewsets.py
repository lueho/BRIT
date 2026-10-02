from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import serializers
from rest_framework.viewsets import GenericViewSet

from utils.viewsets import AutoPermModelViewSet, ReadWriteSerializerViewSetMixin


class _ReadSerializer(serializers.Serializer):
    pass


class _WriteSerializer(serializers.Serializer):
    pass


class _ReadWriteViewSet(ReadWriteSerializerViewSetMixin, GenericViewSet):
    serializer_class = _ReadSerializer
    write_serializer_class = _WriteSerializer


class ReadWriteSerializerViewSetMixinTests(TestCase):
    def _viewset(self, action):
        viewset = _ReadWriteViewSet()
        viewset.action = action
        return viewset

    def test_write_actions_use_write_serializer(self):
        for action in ("create", "update", "partial_update"):
            with self.subTest(action=action):
                self.assertIs(
                    self._viewset(action).get_serializer_class(), _WriteSerializer
                )

    def test_read_actions_use_read_serializer(self):
        for action in ("list", "retrieve", "destroy"):
            with self.subTest(action=action):
                self.assertIs(
                    self._viewset(action).get_serializer_class(), _ReadSerializer
                )


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
