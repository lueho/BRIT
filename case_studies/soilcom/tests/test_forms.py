from django.contrib.auth.models import User
from django.test import TestCase

from maps.models import Catchment
from materials.models import MaterialGroup
from ..forms import CollectionModelForm
from ..models import Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream


class TestCollectionModelForm(TestCase):

    def setUp(self):
        self.owner = User.objects.create(username='owner', password='very-secure!')
        self.catchment = Catchment.objects.create(owner=self.owner, name='Catchment')
        self.collector = Collector.objects.create(owner=self.owner, name='Collector')
        self.collection_system = CollectionSystem.objects.create(owner=self.owner, name='System')
        self.waste_category = WasteCategory.objects.create(owner=self.owner, name='Category')
        self.material_group = MaterialGroup.objects.create(owner=self.owner, name='Biowaste component')
        self.material1 = WasteComponent.objects.create(owner=self.owner, name='Material 1')
        self.material1.groups.add(self.material_group)
        self.material2 = WasteComponent.objects.create(owner=self.owner, name='Material 2')
        self.material2.groups.add(self.material_group)

    def test_waste_stream_get_or_create_on_save(self):
        form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'flyer_url': 'https://www.great-test-flyers.com',
            'description': 'This is a test case'
        })
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        instance = form.save()
        self.assertIsInstance(instance, Collection)
        self.assertEqual(instance.name, f'{self.catchment} {self.waste_category} {self.collection_system}')
        self.assertIsInstance(instance.flyer, WasteFlyer)
        self.assertEqual(instance.flyer.url, 'https://www.great-test-flyers.com')
        self.assertIsInstance(instance.waste_stream, WasteStream)
        self.assertEqual(instance.waste_stream.category.id, self.waste_category.id)

        equal_form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'flyer_url': 'https://www.great-test-flyers.com',
            'description': 'This is a test case'
        })
        self.assertTrue(equal_form.is_valid())
        equal_form.instance.owner = self.owner
        instance2 = equal_form.save()
        self.assertIsInstance(instance2.waste_stream, WasteStream)
        self.assertEqual(instance2.waste_stream.category.id, self.waste_category.id)
        self.assertEqual(instance2.waste_stream.id, instance.waste_stream.id)
        self.assertEqual(len(WasteStream.objects.all()), 1)

    def test_waste_flyer_get_or_create_on_save(self):
        form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'flyer_url': 'https://www.great-test-flyers.com',
            'description': 'This is a test case'
        })
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        instance = form.save()

        equal_form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'flyer_url': 'https://www.great-test-flyers.com',
            'description': 'This is a test case'
        })
        self.assertTrue(equal_form.is_valid())
        equal_form.instance.owner = self.owner
        instance2 = equal_form.save()
        self.assertIsInstance(instance2.flyer, WasteFlyer)
        self.assertEqual(instance2.flyer.id, instance.flyer.id)
        self.assertEqual(instance2.flyer.url, instance.flyer.url)
        self.assertEqual(len(WasteFlyer.objects.all()), 1)
