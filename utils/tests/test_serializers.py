from django.test import TestCase
from rest_framework import serializers

from sources.waste_collection.models import Collector
from utils.serializers import FieldLabelModelSerializer


class FieldLabelModelSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        class TestSerializer(FieldLabelModelSerializer):
            name = serializers.CharField(label="Collector name")
            website = serializers.CharField(label="Website URL")

            class Meta:
                model = Collector
                fields = ("name", "website")

        cls.serializer = TestSerializer
        cls.object = Collector.objects.create(
            name="Test collector", website="https://www.flyer.org"
        )

    def test_field_labels_as_keys_defaults_to_false(self):
        serializer = self.serializer(self.object)
        self.assertFalse(serializer.field_labels_as_keys)

    def test_to_representation_uses_field_names_by_default(self):
        serializer = self.serializer(self.object)
        self.assertDictEqual(
            serializer.data,
            {"name": "Test collector", "website": "https://www.flyer.org"},
        )

    def test_to_representation_uses_field_labels_on_keyword_argument(self):
        serializer = self.serializer(self.object, field_labels_as_keys=True)
        self.assertTrue(serializer.field_labels_as_keys)
        self.assertDictEqual(
            serializer.data,
            {
                "Collector name": "Test collector",
                "Website URL": "https://www.flyer.org",
            },
        )
