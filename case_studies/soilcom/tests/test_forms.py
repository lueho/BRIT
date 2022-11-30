from django.forms import formset_factory
from django.test import TestCase

from materials.models import MaterialCategory
from ..forms import CollectionModelForm, BaseWasteFlyerUrlFormSet, WasteFlyerModelForm
from ..models import (Collection, CollectionCatchment, Collector, CollectionFrequency, CollectionSystem, WasteCategory,
                      WasteComponent, WasteFlyer, WasteStream)


class TestCollectionModelForm(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name='Catchment')
        cls.collector = Collector.objects.create(name='Collector')
        cls.collection_system = CollectionSystem.objects.create(name='System')
        cls.waste_category = WasteCategory.objects.create(name='Category')
        cls.material_group = MaterialCategory.objects.create(name='Biowaste component')
        cls.material1 = WasteComponent.objects.create(name='Material 1')
        cls.material1.categories.add(cls.material_group)
        cls.material2 = WasteComponent.objects.create(name='Material 2')
        cls.material2.categories.add(cls.material_group)
        cls.frequency = CollectionFrequency.objects.create(name='fix')
        waste_stream = WasteStream.objects.create(
            category=cls.waste_category,
        )
        waste_stream.allowed_materials.set([cls.material1, cls.material2])
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=cls.frequency
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
        form.instance.owner = self.collection.owner
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
        equal_form.instance.owner = self.collection.owner
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
        form.instance.owner = self.collection.owner
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
        flyer_1 = WasteFlyer.objects.create(
            url='https://www.test-flyers.org'
        )
        flyer_2 = WasteFlyer.objects.create(
            url='https://www.best-flyers.org'
        )
        flyer_3 = WasteFlyer.objects.create(
            url='https://www.rest-flyers.org'
        )
        CollectionCatchment.objects.create(name='Catchment')
        collector = Collector.objects.create(name='Collector')
        collection_system = CollectionSystem.objects.create(name='System')
        waste_category = WasteCategory.objects.create(name='Category')
        material_group = MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Material 1')
        material1.categories.add(material_group)
        material2 = WasteComponent.objects.create(name='Material 2')
        material2.categories.add(material_group)
        waste_stream = WasteStream.objects.create(
            category=waste_category,
        )
        waste_stream.allowed_materials.set([material1, material2])
        cls.collection = Collection.objects.create(
            name='collection1',
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        cls.collection.flyers.set([flyer_1, flyer_2])
        cls.collection.flyers.add(flyer_3)
        collection2 = Collection.objects.create(
            name='collection2',
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        collection2.flyers.set([flyer_1, flyer_2])

    def test_associated_flyer_urls_are_shown_as_initial_values(self):
        initial_urls = [{'url': flyer.url} for flyer in self.collection.flyers.all()]
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet, extra=0)
        formset = WasteFlyerModelFormSet(parent_object=self.collection, initial=initial_urls)
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
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet)
        formset = WasteFlyerModelFormSet(parent_object=self.collection, data=data)
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
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet)
        formset = WasteFlyerModelFormSet(parent_object=self.collection, owner=self.collection.owner, data=data)
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
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet)
        formset = WasteFlyerModelFormSet(parent_object=self.collection, owner=self.collection.owner, data=data)
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
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet)
        formset = WasteFlyerModelFormSet(parent_object=self.collection,data=data)
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(url=initial_urls[2]['url'])
        self.assertEqual(original_flyer_count - 1, WasteFlyer.objects.count())
        self.assertEqual(original_flyer_count - 1, self.collection.flyers.count())

    def test_save_two_new_and_equal_urls_only_once(self):
        WasteFlyerModelFormSet = formset_factory(WasteFlyerModelForm, formset=BaseWasteFlyerUrlFormSet)
        url = 'https://www.fest-flyers.org'
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': url,
            'form-1-url': url,
        }
        formset = WasteFlyerModelFormSet(data=data, parent_object=self.collection)
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        # get raises an error if the query returns more than one instance
        WasteFlyer.objects.get(url=url)
        # one should be deleted and one created ==> +-0
        self.assertEqual(original_flyer_count, WasteFlyer.objects.count())
