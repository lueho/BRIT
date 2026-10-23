from django.test import TestCase
from rest_framework import serializers
from rest_framework.viewsets import GenericViewSet

from utils.viewsets import ReadWriteSerializerViewSetMixin


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
