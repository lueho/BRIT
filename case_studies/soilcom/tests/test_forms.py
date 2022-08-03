from django.contrib.auth.models import User
from django.forms import formset_factory
from django.test import TestCase

from maps.models import Catchment
from materials.models import MaterialCategory
from users.models import get_default_owner
from ..forms import CollectionModelForm, UrlForm, BaseWasteFlyerUrlFormSet
from ..models import (Collection, Collector, CollectionFrequency, CollectionSystem, WasteCategory, WasteComponent,
                      WasteFlyer, WasteStream)


class TestCollectionModelForm(TestCase):

    def setUp(self):
        self.owner = User.objects.create(username='owner', password='very-secure!')
        self.catchment = Catchment.objects.create(owner=self.owner, name='Catchment')
        self.collector = Collector.objects.create(owner=self.owner, name='Collector')
        self.collection_system = CollectionSystem.objects.create(owner=self.owner, name='System')
        self.waste_category = WasteCategory.objects.create(owner=self.owner, name='Category')
        self.material_group = MaterialCategory.objects.create(owner=self.owner, name='Biowaste component')
        self.material1 = WasteComponent.objects.create(owner=self.owner, name='Material 1')
        self.material1.categories.add(self.material_group)
        self.material2 = WasteComponent.objects.create(owner=self.owner, name='Material 2')
        self.material2.categories.add(self.material_group)
        self.frequency = CollectionFrequency.objects.create(owner=self.owner, name='fix')
        waste_stream = WasteStream.objects.create(
            owner=self.owner,
            category=self.waste_category,
        )
        waste_stream.allowed_materials.set([self.material1, self.material2])
        self.collection = Collection.objects.create(
            owner=self.owner,
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.collection_system,
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=self.frequency
        )

    def test_form_errors(self):
        data = {
            'connection_rate_year': 123
        }
        form = CollectionModelForm(instance=self.collection, data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['catchment'][0], 'This field is required.')
        self.assertEqual(form.errors['collection_system'][0], 'This field is required.')
        self.assertEqual(form.errors['waste_category'][0], 'This field is required.')
        self.assertEqual(form.errors['allowed_materials'][0], 'This field is required.')
        self.assertEqual('Year needs to be in YYYY format.', form.errors['connection_rate_year'][0])

    def test_waste_stream_get_or_create_on_save(self):
        form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'connection_rate': 70,
            'connection_rate_year': 2020,
            'frequency': self.frequency.id,
            'description': 'This is a test case'
        })
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        instance = form.save()
        self.assertIsInstance(instance, Collection)
        self.assertEqual(instance.name, f'{self.catchment} {self.waste_category} {self.collection_system}')
        self.assertIsInstance(instance.waste_stream, WasteStream)
        self.assertEqual(instance.waste_stream.category.id, self.waste_category.id)

        equal_form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'frequency': self.frequency.id,
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

    def test_connection_rate_percentage_is_converted_to_fraction(self):
        form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
            'connection_rate': 70,
            'connection_rate_year': 2020,
            'frequency': self.frequency.id,
            'description': 'This is a test case'
        })
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        instance = form.save()
        self.assertEqual(0.7, instance.connection_rate)

    def test_connection_rate_is_converted_to_percentage_for_initial_values(self):
        form = CollectionModelForm(instance=self.collection)
        self.assertEqual(form.initial['connection_rate'], self.collection.connection_rate * 100)

    def test_missing_connection_rate_does_not_cause_type_error(self):
        self.collection.connection_rate = None
        CollectionModelForm(instance=self.collection)


class WasteFlyerUrlFormSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        flyer_1 = WasteFlyer.objects.create(
            owner=owner,
            url='https://www.test-flyers.org'
        )
        flyer_2 = WasteFlyer.objects.create(
            owner=owner,
            url='https://www.best-flyers.org'
        )
        flyer_3 = WasteFlyer.objects.create(
            owner=owner,
            url='https://www.rest-flyers.org'
        )
        Catchment.objects.create(owner=owner, name='Catchment')
        collector = Collector.objects.create(owner=owner, name='Collector')
        collection_system = CollectionSystem.objects.create(owner=owner, name='System')
        waste_category = WasteCategory.objects.create(owner=owner, name='Category')
        material_group = MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Material 1')
        material1.categories.add(material_group)
        material2 = WasteComponent.objects.create(owner=owner, name='Material 2')
        material2.categories.add(material_group)
        waste_stream = WasteStream.objects.create(
            owner=owner,
            category=waste_category,
        )
        waste_stream.allowed_materials.set([material1, material2])
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        collection1.flyers.set([flyer_1, flyer_2])
        collection1.flyers.add(flyer_3)
        collection2 = Collection.objects.create(
            owner=owner,
            name='collection2',
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        collection2.flyers.set([flyer_1, flyer_2])

    def setUp(self):
        self.owner = get_default_owner()
        self.collection = Collection.objects.get(name='collection1')

    def test_associated_flyer_urls_are_shown_as_initial_values(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet, extra=0)
        formset = UrlFormSet(parent_object=self.collection)
        displayed_urls = [form.initial for form in formset]
        self.assertListEqual(initial_urls, displayed_urls)

    def test_initial_flyers_remain_associated_with_parent_collection(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            'form-INITIAL_FORMS': 3,
            'form-TOTAL_FORMS': 3,
            'form-0-url': initial_urls[0]['url'],
            'form-1-url': initial_urls[1]['url'],
            'form-2-url': initial_urls[2]['url']
        }
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet)
        formset = UrlFormSet(parent_object=self.collection, data=data)
        self.assertTrue(formset.is_valid())
        formset.save()
        for url in initial_urls:
            WasteFlyer.objects.get(url=url['url'])
        self.assertEqual(len(initial_urls), self.collection.flyers.count())

    def test_flyers_are_created_from_unknown_urls_and_associated_with_parent_collection(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            'form-INITIAL_FORMS': 3,
            'form-TOTAL_FORMS': 4,
            'form-0-url': initial_urls[0]['url'],
            'form-1-url': initial_urls[1]['url'],
            'form-2-url': initial_urls[2]['url'],
            'form-3-url': 'https://www.fest-flyers.org',
        }
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet)
        formset = UrlFormSet(parent_object=self.collection, owner=self.owner, data=data)
        self.assertTrue(formset.is_valid())
        formset.save()
        WasteFlyer.objects.get(url='https://www.fest-flyers.org')
        self.assertEqual(len(initial_urls) + 1, self.collection.flyers.count())

    def test_flyers_removed_from_this_collection_but_connected_to_another_are_preserved(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            'form-INITIAL_FORMS': 3,
            'form-TOTAL_FORMS': 3,
            'form-0-url': initial_urls[0]['url'],
            'form-1-url': '',
            'form-2-url': initial_urls[2]['url'],
        }
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet)
        formset = UrlFormSet(parent_object=self.collection, owner=self.owner, data=data)
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        WasteFlyer.objects.get(url=initial_urls[1]['url'])
        self.assertEqual(original_flyer_count - 1, self.collection.flyers.count())
        self.assertEqual(original_flyer_count, WasteFlyer.objects.count())

    def test_completely_unused_flyers_get_deleted(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            'form-INITIAL_FORMS': 3,
            'form-TOTAL_FORMS': 3,
            'form-0-url': initial_urls[0]['url'],
            'form-1-url': initial_urls[1]['url'],
            'form-2-url': '',
        }
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet)
        formset = UrlFormSet(parent_object=self.collection, owner=self.owner, data=data)
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(url=initial_urls[2]['url'])
        self.assertEqual(original_flyer_count - 1, WasteFlyer.objects.count())
        self.assertEqual(original_flyer_count - 1, self.collection.flyers.count())

    def test_save_two_new_and_equal_urls_only_once(self):
        UrlFormSet = formset_factory(UrlForm, formset=BaseWasteFlyerUrlFormSet)
        url = 'https://www.fest-flyers.org'
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': url,
            'form-1-url': url,
        }
        formset = UrlFormSet(data=data, parent_object=self.collection, owner=self.owner)
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        # get raises an error if the query returns more than one instance
        WasteFlyer.objects.get(url=url)
        # one should be deleted and one created ==> +-0
        self.assertEqual(original_flyer_count, WasteFlyer.objects.count())
