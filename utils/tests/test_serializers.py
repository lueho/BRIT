from django.test import TestCase
from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import ModelSerializer, Serializer

from sources.waste_collection.models import Collector
from utils.serializers import FieldLabelMixin


class FieldLabelMixinTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        class TestSerializer(FieldLabelMixin, Serializer):
            char = CharField(label="Text")
            integer = IntegerField(label="Number")

        cls.data = {"char": "abc", "integer": 123}
        cls.serializer = TestSerializer

        class TestModelSerializer(ModelSerializer):
            class Meta:
                model = Collector
                fields = ("name", "website")

        cls.model_serializer = TestModelSerializer
        cls.tdata = {"name": "Test collector", "website": "https://www.flyer.org"}
        cls.object = Collector.objects.create(**cls.tdata)

    def test_serializer_init_sets_label_names_as_keys_attribute(self):
        serializer = self.serializer(field_labels_as_keys=True)
        self.assertTrue(hasattr(serializer, "field_labels_as_keys"))
        self.assertTrue(serializer.field_labels_as_keys)

    def test_field_labels_as_keys_default_to_false(self):
        serializer = self.serializer()
        self.assertTrue(hasattr(serializer, "field_labels_as_keys"))
        self.assertFalse(serializer.field_labels_as_keys)

    def test_serializer_to_representation_uses_field_names_by_default(self):
        serializer = self.serializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertDictEqual(serializer.validated_data, self.data)
        self.assertDictEqual(serializer.data, self.data)

    def test_serializer_to_representation_uses_field_labels_on_keyword_argument(self):
        serializer = self.serializer(data=self.data, field_labels_as_keys=True)
        self.assertTrue(serializer.field_labels_as_keys)

        expected = {"Text": "abc", "Number": 123}
        self.assertTrue(serializer.is_valid())
        self.assertTrue(serializer.field_labels_as_keys)
        self.assertDictEqual(serializer.validated_data, self.data)
        self.assertDictEqual(serializer.data, expected)

    def test_model_serializer_to_representation_uses_field_names_by_default(self):
        serializer = self.model_serializer(self.object)
        self.assertDictEqual(serializer.data, self.tdata)
