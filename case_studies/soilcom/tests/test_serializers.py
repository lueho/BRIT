from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from rest_framework.serializers import ModelSerializer, Serializer, CharField, IntegerField

from maps.models import Catchment, NutsRegion, LauRegion
from maps.serializers import FieldLabelMixin
from materials.models import MaterialCategory

from ..models import (
    Collection,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream
)
from ..serializers import CollectionModelSerializer, CollectionFlatSerializer


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
            name='Test Collection',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            frequency=frequency,
            connection_rate=0.7,
            connection_rate_year=2020,
            description='This is a test case.'
        )
        collection.flyers.add(waste_flyer_1)
        collection.flyers.add(waste_flyer_2)

    def setUp(self):
        self.collection = Collection.objects.get(name='Test Collection')

    def test_multiple_sources_in_representation(self):
        serializer = CollectionModelSerializer(self.collection)
        flyer_urls = serializer.data['sources']
        self.assertIsInstance(flyer_urls, list)
        self.assertEqual(len(flyer_urls), 2)
        for url in flyer_urls:
            self.assertIsInstance(url, str)

    def test_connection_rate_is_converted_and_connected_with_year(self):
        serializer = CollectionModelSerializer(self.collection)
        connection_rate = serializer.data['connection_rate']
        self.assertEqual('70.0% (2020)', connection_rate)

    def test_connection_rate_non_returns_without_error(self):
        self.collection.connection_rate = None
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        self.assertIsNone(serializer.data['connection_rate'])

    def test_connection_rate_returns_without_year_if_year_is_not_given(self):
        self.collection.connection_rate_year = None
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        self.assertEqual('70.0%', serializer.data['connection_rate'])


class CollectionFlatSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test Category'),
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

        nutsregion = NutsRegion.objects.create(owner=owner, name='Hamburg', cntr_code='DE', nuts_id='DE600')
        catchment1 = Catchment.objects.create(owner=owner, name='Test Catchment', region=nutsregion.region_ptr)
        collection1 = Collection.objects.create(
            owner=owner,
            created_by=owner,
            lastmodified_by=owner,
            name='Test Collection Nuts',
            catchment=catchment1,
            collector=Collector.objects.create(owner=owner, name='Test Collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test System'),
            waste_stream=waste_stream,
            frequency=frequency,
            connection_rate=0.7,
            connection_rate_year=2020,
            description='This is a test case.'
        )
        collection1.flyers.add(waste_flyer_1)
        collection1.flyers.add(waste_flyer_2)

        lauregion = LauRegion.objects.create(owner=owner, name='Shetland Islands', cntr_code='UK', lau_id='S30000041')
        catchment2 = Catchment.objects.create(owner=owner, name='Test Catchment', region=lauregion.region_ptr)
        collection2 = Collection.objects.create(
            owner=owner,
            created_by=owner,
            lastmodified_by=owner,
            name='Test Collection Lau',
            catchment=catchment2,
            collector=Collector.objects.create(owner=owner, name='Test Collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test System'),
            waste_stream=waste_stream,
            frequency=frequency,
            connection_rate=0.7,
            connection_rate_year=2020,
            description='This is a test case.'
        )
        collection2.flyers.add(waste_flyer_1)
        collection2.flyers.add(waste_flyer_2)

    def setUp(self):
        self.collection_nuts = Collection.objects.get(name='Test Collection Nuts')
        self.collection_lau = Collection.objects.get(name='Test Collection Lau')

    def test_serializer_data_contains_all_fields(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        keys = {'catchment', 'nuts_or_lau_id', 'collector', 'collection_system', 'country', 'waste_category',
                'allowed_materials', 'connection_rate', 'connection_rate_year', 'frequency', 'comments', 'sources',
                'created_by', 'created_at', 'lastmodified_by', 'lastmodified_at'}
        self.assertSetEqual(keys, set(serializer.data.keys()))

    def test_serializer_gets_information_from_foreign_keys_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual('Test Catchment', serializer.data['catchment'])
        self.assertEqual('Test Collector', serializer.data['collector'])
        self.assertEqual('Test System', serializer.data['collection_system'])
        self.assertEqual('Test Category', serializer.data['waste_category'])
        self.assertEqual('Test material 1, Test material 2', serializer.data['allowed_materials'])
        self.assertEqual('Test Frequency', serializer.data['frequency'])
        self.assertEqual('https://www.test-flyer.org, https://www.best-flyer.org', serializer.data['sources'])
        self.assertEqual('owner', serializer.data['created_by'])
        self.assertEqual()
        self.assertEqual('owner', serializer.data['lastmodified_by'])

    def test_nuts_id_is_read_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual('DE600', serializer.data['nuts_or_lau_id'])

    def test_country_is_read_correctly_from_nutsregion(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual('DE', serializer.data['country'])

    def test_lau_id_is_read_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_lau)
        self.assertEqual('S30000041', serializer.data['nuts_or_lau_id'])

    def test_country_is_read_correctly_from_lauregion(self):
        serializer = CollectionFlatSerializer(self.collection_lau)
        self.assertEqual('UK', serializer.data['country'])
