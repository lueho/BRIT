from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Source
from distributions.models import Timestep
from users.models import get_default_owner

from ..models import MaterialComponent, MaterialComponentGroup, MaterialProperty, MaterialPropertyValue, Composition, Material, SampleSeries, Sample, WeightShare
from ..serializers import (
    CompositionModelSerializer,
    MaterialPropertyValueModelSerializer,
    SampleSeriesModelSerializer,
    SampleModelSerializer,
    WeightShareModelSerializer
)


class MaterialPropertySerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        prop = MaterialProperty.objects.create(
            owner=owner,
            name='Test Property',
            unit='Test Unit'
        )
        MaterialPropertyValue.objects.create(
            owner=owner,
            property=prop,
            average=123.321,
            standard_deviation=0.1337
        )

    def setUp(self):
        self.value = MaterialPropertyValue.objects.get(standard_deviation=0.1337)

    def test_serializer(self):
        request = RequestFactory().get(reverse('home'))
        data = MaterialPropertyValueModelSerializer(self.value, context={'request': request}).data
        self.assertIn('id', data)
        self.assertIn('property_name', data)
        self.assertIn('property_url', data)
        self.assertIn('average', data)
        self.assertIn('standard_deviation', data)
        self.assertIn('unit', data)


class SampleSeriesModelSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_serializer_construction(self):
        data = SampleSeriesModelSerializer(self.series).data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('distributions', data)


class SampleSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(owner=owner, name='Test Sample', series=series, timestep=Timestep.objects.default())
        source = Source.objects.create(owner=owner, title='Test Source')
        sample.sources.add(source)

    def setUp(self):
        self.sample = Sample.objects.get(name='Test Sample')

    def test_serializer_construction(self):
        request = RequestFactory().get(reverse('sample-detail', kwargs={'pk': self.sample.id}))
        data = SampleModelSerializer(self.sample, context={'request': request}).data
        self.assertIn('name', data)
        self.assertEqual(data['name'], 'Test Sample')
        self.assertIn('material_name', data)
        self.assertEqual(data['material_name'], 'Test Material')
        self.assertIn('material_url', data)
        self.assertIn('series_name', data)
        self.assertEqual(data['series_name'], 'Test Series')
        self.assertIn('series_url', data)
        self.assertIn('timestep', data)
        self.assertIn('taken_at', data)
        self.assertIn('preview', data)
        self.assertIn('compositions', data)
        self.assertIn('properties', data)
        self.assertIn('sources', data)


class CompositionSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(
            owner=owner,
            name='Test Sample',
            series=series,
            timestep=Timestep.objects.default()
        )
        group = MaterialComponentGroup.objects.create(owner=owner, name='Test Group')
        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=sample,
            fractions_of=MaterialComponent.objects.default()
        )
        composition.add_component(MaterialComponent.objects.other(), average=0.5, standard_deviation=0.1337)

    def setUp(self):
        self.composition = Composition.objects.get(group__name='Test Group', sample__name='Test Sample')

    def test_serializer_construction(self):
        data = CompositionModelSerializer(self.composition).data
        self.assertIn('group', data)
        self.assertIn('group_name', data)
        self.assertIn('sample', data)
        self.assertIn('fractions_of', data)
        self.assertIn('fractions_of_name', data)
        self.assertIn('shares', data)

    def test_other_component_is_last_in_the_shares_list(self):
        data = CompositionModelSerializer(self.composition).data
        self.assertEqual(data['shares'][-1]['component'], MaterialComponent.objects.other().pk)


class WeightShareModelSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(
            owner=owner,
            name='Test Sample',
            series=series,
            timestep=Timestep.objects.default()
        )
        group = MaterialComponentGroup.objects.create(owner=owner, name='Test Group')
        composition = Composition.objects.create(
            owner=owner,
            name='Test Composition',
            group=group,
            sample=sample,
            fractions_of=MaterialComponent.objects.default()
        )
        WeightShare.objects.create(
            owner=owner,
            component=MaterialComponent.objects.default(),
            composition=composition,
            average=0.9,
            standard_deviation=0.1337
        )

    def setUp(self):
        self.share = WeightShare.objects.get(standard_deviation=0.1337)

    def test_serializer_construction(self):
        data = WeightShareModelSerializer(self.share).data
        self.assertIn('component', data)
        self.assertIn('component_name', data)
        self.assertIn('average', data)
        self.assertIn('standard_deviation', data)
