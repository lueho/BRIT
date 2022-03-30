from django.contrib.auth.models import User
from django.forms import modelformset_factory
from django.test import TestCase

from maps.models import Catchment
from materials.models import MaterialCategory
from ..forms import CollectionModelForm, WasteFlyerModelForm, WasteFlyerModelFormSet
from ..models import Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream


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

    def test_missing_data_errors(self):
        waste_stream = WasteStream.objects.create(
            owner=self.owner,
            category=self.waste_category,
        )
        waste_stream.allowed_materials.set([self.material1, self.material2])
        collection = Collection.objects.create(
            owner=self.owner,
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.collection_system,
            waste_stream=waste_stream
        )
        form = CollectionModelForm(instance=collection, data={})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['catchment'][0], 'This field is required.')
        self.assertEqual(form.errors['collection_system'][0], 'This field is required.')
        self.assertEqual(form.errors['waste_category'][0], 'This field is required.')
        self.assertEqual(form.errors['allowed_materials'][0], 'This field is required.')

    def test_waste_stream_get_or_create_on_save(self):
        form = CollectionModelForm(data={
            'catchment': self.catchment.id,
            'collector': self.collector.id,
            'collection_system': self.collection_system.id,
            'waste_category': self.waste_category.id,
            'allowed_materials': [self.material1.id, self.material2.id],
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


class TestWasteFlyerModelForm(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')

    def setUp(self):
        self.owner = User.objects.get(username='owner')

    def test_valid_on_minimal_input(self):
        data = {
            'url': 'https://www.test-flyers.org'
        }
        form = WasteFlyerModelForm(data=data)
        self.assertTrue(form.is_valid())

    def test_save_creates_new_flyer_instance_if_url_is_new(self):
        data = {
            'url': 'https://www.test-flyers.org'
        }
        form = WasteFlyerModelForm(data=data)
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        form.save()
        flyer = WasteFlyer.objects.get(url='https://www.test-flyers.org')
        self.assertIsInstance(flyer, WasteFlyer)
        self.assertEqual(len(WasteFlyer.objects.all()), 1)

    def test_save_returns_existing_flyer_if_url_exists(self):
        existing_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            url='https://www.this-flyer-already-exists.org'
        )
        data = {
            'url': 'https://www.this-flyer-already-exists.org'
        }
        form = WasteFlyerModelForm(data=data)
        self.assertTrue(form.is_valid())
        form.instance.owner = self.owner
        new_flyer = form.save()
        self.assertTrue(new_flyer == existing_flyer)
        self.assertEqual(len(WasteFlyer.objects.all()), 1)


class WasteFlyerModelFormSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure')
        used_flyer = WasteFlyer.objects.create(
            owner=owner,
            url='https://www.test-flyers.org'
        )
        WasteFlyer.objects.create(
            owner=owner,
            url='https://www.best-flyers.org'
        )
        WasteFlyer.objects.create(
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
        collection1.flyers.set([used_flyer])
        collection2 = Collection.objects.create(
            owner=owner,
            name='collection2',
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        collection2.flyers.set([used_flyer])

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.collection = Collection.objects.get(name='collection1')
        self.used_flyer = WasteFlyer.objects.get(url='https://www.test-flyers.org')

    def test_construct_initial_formset_with_custom_modelform(self):
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        flyers = WasteFlyer.objects.all()
        formset = FormSet(queryset=flyers)
        self.assertEqual(len(formset), 3)

    def test_save_two_new_and_equal_urls_only_once(self):
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': 'https://www.fest-flyers.org',
            'form-0-id': '',
            'form-1-url': 'https://www.fest-flyers.org',
            'form-1-id': '',
        }
        formset = FormSet(data=data, parent_object=self.collection)
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        # The following should raise an exception if two flyers with equal urls where created
        WasteFlyer.objects.get(url='https://www.fest-flyers.org')
        self.assertEqual(len(WasteFlyer.objects.all()), 4)

    def test_empty_form_is_ignored(self):
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': 'https://www.fest-flyers.org',
            'form-0-id': '',
            'form-1-url': '',
            'form-1-id': '',
        }
        formset = FormSet(data=data)
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        self.assertEqual(len(WasteFlyer.objects.all()), 4)

    def test_changing_url_of_existing_flyer_to_blank_doesnt_create_blank_flyer(self):
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        existing_flyer = WasteFlyer.objects.first()
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': '',
            'form-0-id': f'{existing_flyer.id}',
            'form-1-url': '',
            'form-1-id': '',
        }
        formset = FormSet(data=data, parent_object=self.collection)
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(url='')
        self.assertEqual(len(WasteFlyer.objects.all()), 3)

    def test_changing_url_of_existing_flyer_removes_association_with_collection(self):
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': '',
            'form-0-id': f'{self.used_flyer.id}',
            'form-1-url': '',
            'form-1-id': '',
        }
        formset = FormSet(data=data, parent_object=self.collection)
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        WasteFlyer.objects.get(id=self.used_flyer.id)
        self.assertFalse(self.collection.flyers.exists())
        self.assertTrue(self.used_flyer.collections.exists())
        self.assertEqual(len(WasteFlyer.objects.all()), 3)

    def test_changing_url_of_existing_flyer_deletes_flyer_if_not_used_elsewhere(self):
        collection2 = Collection.objects.get(name='collection2')
        collection2.flyers.remove(self.used_flyer)
        FormSet = modelformset_factory(
            WasteFlyer,
            form=WasteFlyerModelForm,
            formset=WasteFlyerModelFormSet,
            extra=0
        )
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': '',
            'form-0-id': f'{self.used_flyer.id}',
            'form-1-url': '',
            'form-1-id': '',
        }
        formset = FormSet(data=data, parent_object=self.collection)
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(id=self.used_flyer.id)
        self.assertEqual(len(WasteFlyer.objects.all()), 2)
