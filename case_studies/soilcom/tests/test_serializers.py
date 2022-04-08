from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from rest_framework.serializers import ModelSerializer, Serializer, CharField, IntegerField

from maps.models import Catchment
from maps.serializers import FieldLabelMixin
from materials.models import MaterialCategory
from ..models import Collector, WasteComponent, WasteStream, WasteCategory, WasteFlyer, CollectionSystem, Collection, CollectionFrequency
from ..serializers import CollectionModelSerializer


class FieldLabelMixinTestCase(TestCase):

    def setUp(self):
        class TestSerializer(FieldLabelMixin, Serializer):
            char = CharField(label='Text')
            integer = IntegerField(label='Number')

        self.data = {'char': 'abc', 'integer': 123}
        self.serializer = TestSerializer

        class TestModel(models.Model):
            char = models.CharField(verbose_name='Text')
            integer = models.IntegerField(verbose_name='Number')

        class TestModelSerializer(ModelSerializer):
            class Meta:
                model = Collector
                fields = ('name', 'website')

        self.model_serializer = TestModelSerializer
        self.model = TestModel
        # self.object = TestModel.objects.create(**self.data)
        owner = User.objects.create(username='owner', password='very-secure!')
        self.tdata = {'name': 'Test collector', 'website': 'https://www.flyer.org'}
        self.object = Collector.objects.create(owner=owner, **self.tdata)

    def test_serializer_init_sets_label_names_as_keys_attribute(self):
        serializer = self.serializer(field_labels_as_keys=True)
        self.assertTrue(hasattr(serializer, 'field_labels_as_keys'))
        self.assertTrue(serializer.field_labels_as_keys)

    def test_field_labels_as_keys_default_to_false(self):
        serializer = self.serializer()
        self.assertTrue(hasattr(serializer, 'field_labels_as_keys'))
        self.assertFalse(serializer.field_labels_as_keys)

    def test_serializer_to_representation_uses_field_names_by_default(self):
        serializer = self.serializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertDictEqual(serializer.validated_data, self.data)
        self.assertDictEqual(serializer.data, self.data)

    def test_serializer_to_representation_uses_field_labels_on_keyword_argument(self):
        serializer = self.serializer(data=self.data, field_labels_as_keys=True)
        self.assertTrue(serializer.field_labels_as_keys)

        expected = {'Text': 'abc', 'Number': 123}
        self.assertTrue(serializer.is_valid())
        self.assertTrue(serializer.field_labels_as_keys)
        self.assertDictEqual(serializer.validated_data, self.data)
        self.assertDictEqual(serializer.data, expected)

    def test_model_serializer_to_representation_uses_field_names_by_default(self):
        # obj = self.model(**self.data)
        # obj = self.object
        obj = Collector.objects.all()
        # self.assertEqual(obj.char, self.data['char'])
        # self.assertEqual(obj.integer, self.data['integer'])
        # self.assertIsInstance(obj, self.model)
        # self.assertEqual(obj.name, self.tdata['name'])
        # self.assertEqual(obj.website, self.tdata['website'])
        # self.assertIsInstance(obj, Collector)
        serializer = self.model_serializer(obj, many=True)
        # self.assertTrue(serializer.is_valid())
        # self.assertDictEqual(serializer.validated_data, self.data)
        self.assertDictEqual(serializer.data[0], self.tdata)


class CollectionSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer_1 = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        waste_flyer_2 = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer456',
            url='https://www.best-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        collection = Collection.objects.create(
            owner=owner,
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            frequency=frequency,
            description='This is a test case.'
        )
        collection.flyers.add(waste_flyer_1)
        collection.flyers.add(waste_flyer_2)

    def setUp(self):
        self.collection = Collection.objects.first()

    def test_multiple_sources_in_representation(self):
        serializer = CollectionModelSerializer(Collection.objects.first())
        flyer_urls = serializer.data['sources']
        self.assertIsInstance(flyer_urls, list)
        self.assertEqual(len(flyer_urls), 2)
        for url in flyer_urls:
            self.assertIsInstance(url, str)
