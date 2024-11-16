from decimal import Decimal

from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from distributions.models import Timestep
from ..models import (Composition, Material, MaterialComponent, MaterialComponentGroup, MaterialProperty,
                      MaterialPropertyValue, Sample, SampleSeries, WeightShare)
from ..serializers import (CompositionDoughnutChartSerializer, CompositionModelSerializer,
                           MaterialPropertyValueModelSerializer, SampleModelSerializer, SampleSeriesModelSerializer,
                           WeightShareModelSerializer)


class MaterialPropertySerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        prop = MaterialProperty.objects.create(
            name='Test Property',
            unit='Test Unit'
        )
        MaterialPropertyValue.objects.create(
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
        material = Material.objects.create(name='Test Material')
        SampleSeries.objects.create(name='Test Series', material=material)

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
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(name='Test Sample', series=series,
                                       timestep=Timestep.objects.default())
        with mute_signals(post_save):
            source = Source.objects.create(title='Test Source')
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
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(
            name='Test Sample',
            series=series,
            timestep=Timestep.objects.default()
        )
        group = MaterialComponentGroup.objects.create(name='Test Group')
        composition = Composition.objects.create(
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
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(
            name='Test Sample',
            series=series,
            timestep=Timestep.objects.default()
        )
        group = MaterialComponentGroup.objects.create(name='Test Group')
        composition = Composition.objects.create(
            name='Test Composition',
            group=group,
            sample=sample,
            fractions_of=MaterialComponent.objects.default()
        )
        WeightShare.objects.create(
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


class CompositionDoughnutChartSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(name='Test Sample', series=series)
        group = MaterialComponentGroup.objects.create(name='Test Group')
        composition = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default()
        )
        component1 = MaterialComponent.objects.create(name='Test Component 1')
        component2 = MaterialComponent.objects.create(name='Test Component 2')
        composition.add_component(MaterialComponent.objects.other(), average=0.7, standard_deviation=0.1337)
        composition.add_component(component1, average=0.1, standard_deviation=0.1337)
        composition.add_component(component2, average=0.2, standard_deviation=0.1337)

    def setUp(self):
        self.composition = Composition.objects.get(group__name='Test Group')

    def test_serializer_returns_correct_data(self):
        data = CompositionDoughnutChartSerializer(self.composition).data
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('unit', data)
        self.assertIn('labels', data)
        self.assertIsInstance(data['labels'], list)
        self.assertListEqual(data['labels'], ['Test Component 2', 'Test Component 1', 'Other'])
        self.assertIn('data', data)
        self.assertIsInstance(data['data'], list)
        self.assertIsInstance(data['data'][0]['data'], list)
        self.assertListEqual(
            data['data'][0]['data'],
            [Decimal('0.2000000000'), Decimal('0.1000000000'), Decimal('0.7000000000')]
        )
