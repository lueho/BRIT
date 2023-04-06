from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps
from rest_framework.serializers import ModelSerializer, Serializer, CharField, IntegerField

from maps.models import Attribute, RegionAttributeValue, NutsRegion, LauRegion
from maps.serializers import FieldLabelMixin
from materials.models import MaterialCategory
from users.models import get_default_owner

from ..models import (
    Collection,
    CollectionCatchment,
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

    @classmethod
    def setUp(cls):
        class TestSerializer(FieldLabelMixin, Serializer):
            char = CharField(label='Text')
            integer = IntegerField(label='Number')

        cls.data = {'char': 'abc', 'integer': 123}
        cls.serializer = TestSerializer

        with isolate_apps('case_studies.soilcom'):
            class TestModel(models.Model):
                char = models.CharField(verbose_name='Text')
                integer = models.IntegerField(verbose_name='Number')

        class TestModelSerializer(ModelSerializer):
            class Meta:
                model = Collector
                fields = ('name', 'website')

        cls.model_serializer = TestModelSerializer
        cls.model = TestModel
        # self.object = TestModel.objects.create(**self.data)
        cls.tdata = {'name': 'Test collector', 'website': 'https://www.flyer.org'}
        cls.object = Collector.objects.create(**cls.tdata)

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


class CollectionModelSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        MaterialCategory.objects.create(name='Biowaste component')
        cls.allowed_material_1 = WasteComponent.objects.create(name='Allowed Material 1')
        cls.allowed_material_2 = WasteComponent.objects.create(name='Allowed Material 2')
        cls.forbidden_material_1 = WasteComponent.objects.create(name='Forbidden Material 1')
        cls.forbidden_material_2 = WasteComponent.objects.create(name='Forbidden Material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)

        waste_flyer_1 = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        waste_flyer_2 = WasteFlyer.objects.create(
            abbreviation='WasteFlyer456',
            url='https://www.best-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        cls.collection = Collection.objects.create(
            name='Test Collection',
            catchment=CollectionCatchment.objects.create(name='Test catchment'),
            collector=Collector.objects.create(name='Test collector'),
            collection_system=CollectionSystem.objects.create(name='Test system'),
            waste_stream=waste_stream,
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection.flyers.add(waste_flyer_1)
        cls.collection.flyers.add(waste_flyer_2)

    def test_all_keys_are_present_in_result_data(self):
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('catchment', data)
        self.assertIn('collector', data)
        self.assertIn('collection_system', data)
        self.assertIn('waste_category', data)
        self.assertIn('allowed_materials', data)
        self.assertIn('forbidden_materials', data)
        self.assertIn('frequency', data)
        self.assertIn('sources', data)
        self.assertIn('comments', data)

    def test_multiple_sources_in_representation(self):
        serializer = CollectionModelSerializer(self.collection)
        flyer_urls = serializer.data['sources']
        self.assertIsInstance(flyer_urls, list)
        self.assertEqual(len(flyer_urls), 2)
        for url in flyer_urls:
            self.assertIsInstance(url, str)


class CollectionFlatSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_default_owner()

        MaterialCategory.objects.create(name='Biowaste component')
        cls.allowed_material_1 = WasteComponent.objects.create(name='Allowed Material 1')
        cls.allowed_material_2 = WasteComponent.objects.create(name='Allowed Material 2')
        cls.forbidden_material_1 = WasteComponent.objects.create(name='Forbidden Material 1')
        cls.forbidden_material_2 = WasteComponent.objects.create(name='Forbidden Material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test Category'),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)

        waste_flyer_1 = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        waste_flyer_2 = WasteFlyer.objects.create(
            abbreviation='WasteFlyer456',
            url='https://www.best-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')

        nutsregion = NutsRegion.objects.create(name='Hamburg', country='DE', nuts_id='DE600')
        population = Attribute.objects.create(name='Population', unit='')
        population_density = Attribute.objects.create(name='Population density', unit='1/km')
        RegionAttributeValue(region=nutsregion, attribute=population, value=123321)
        RegionAttributeValue(region=nutsregion, attribute=population_density, value=123.5)
        catchment1 = CollectionCatchment.objects.create(name='Test Catchment', region=nutsregion.region_ptr)
        cls.collection_nuts = Collection.objects.create(
            created_by=cls.owner,
            lastmodified_by=cls.owner,
            name='Test Collection Nuts',
            catchment=catchment1,
            collector=Collector.objects.create(name='Test Collector'),
            collection_system=CollectionSystem.objects.create(name='Test System'),
            waste_stream=waste_stream,
            fee_system='Fixed fee',
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection_nuts.flyers.add(waste_flyer_1)
        cls.collection_nuts.flyers.add(waste_flyer_2)

        lauregion = LauRegion.objects.create(name='Shetland Islands', country='UK', lau_id='S30000041')
        catchment2 = CollectionCatchment.objects.create(name='Test Catchment', region=lauregion.region_ptr)
        cls.collection_lau = Collection.objects.create(
            created_by=cls.owner,
            lastmodified_by=cls.owner,
            name='Test Collection Lau',
            catchment=catchment2,
            collector=Collector.objects.create(name='Test Collector'),
            collection_system=CollectionSystem.objects.create(name='Test System'),
            waste_stream=waste_stream,
            fee_system='Fixed fee',
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection_lau.flyers.add(waste_flyer_1)
        cls.collection_lau.flyers.add(waste_flyer_2)

    def test_serializer_data_contains_all_fields(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        keys = {'catchment', 'nuts_or_lau_id', 'collector', 'collection_system', 'country', 'waste_category',
                'allowed_materials', 'forbidden_materials', 'fee_system',
                'frequency', 'population', 'population_density', 'comments', 'sources', 'created_by',
                'created_at', 'lastmodified_by', 'lastmodified_at'}
        self.assertSetEqual(keys, set(serializer.data.keys()))

    def test_serializer_gets_information_from_foreign_keys_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual('Test Catchment', serializer.data['catchment'])
        self.assertEqual('Test Collector', serializer.data['collector'])
        self.assertEqual('Test System', serializer.data['collection_system'])
        self.assertEqual('Test Category', serializer.data['waste_category'])
        self.assertEqual('Allowed Material 1, Allowed Material 2', serializer.data['allowed_materials'])
        self.assertEqual('Forbidden Material 1, Forbidden Material 2', serializer.data['forbidden_materials'])
        self.assertEqual('Test Frequency', serializer.data['frequency'])
        self.assertEqual('https://www.test-flyer.org, https://www.best-flyer.org', serializer.data['sources'])
        self.assertEqual(self.owner.username, serializer.data['created_by'])
        self.assertEqual(self.owner.username, serializer.data['lastmodified_by'])

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

    def test_newline_characters_are_replaced_with_semicolons_in_comments(self):
        self.collection_nuts.description = 'This \n contains \r no newline \r\n characters.'
        self.collection_nuts.save()
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertNotIn('\n', serializer.data['comments'])
        self.assertNotIn('\r', serializer.data['comments'])
