from datetime import date, timedelta
from factory.django import mute_signals

from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase
from django.urls import reverse

from distributions.models import Period, TemporalDistribution, Timestep
from maps.models import GeoDataset, Region
from materials.models import Material
from users.models import get_default_owner
from utils.tests.testcases import comparable_model_dict
from ..models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency, CollectionSeason,
                      CollectionSystem, WasteCategory, WasteFlyer, WasteStream)


class InitialDataTestCase(TestCase):

    @staticmethod
    def test_simple_initial_collection_frequency_exists():
        season = CollectionSeason.objects.get(
            distribution=TemporalDistribution.objects.get(name='Months of the year'),
            first_timestep=Timestep.objects.get(name='January'),
            last_timestep=Timestep.objects.get(name='December')
        )
        CollectionCountOptions.objects.get(
            frequency__type='Fixed',
            season=season,
            standard=52
        )

    @staticmethod
    def test_household_biowaste_collection_dataset_is_initialized():
        GeoDataset.objects.get(
            owner=get_default_owner(),
            name='Household Biowaste Collection',
            model_name='WasteCollection',
            region=Region.objects.get(name='Europe (NUTS)')
        )


class CollectionCatchmentTestCase(TestCase):
    catchment = None

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name='Test Catchment')
        cls.child_catchment = CollectionCatchment.objects.create(parent=cls.catchment)
        cls.grandchild_catchment = CollectionCatchment.objects.create(parent=cls.child_catchment)
        cls.great_grandchild_catchment = CollectionCatchment.objects.create(parent=cls.grandchild_catchment)
        cls.collection = Collection.objects.create(catchment=cls.catchment)
        cls.child_collection = Collection.objects.create(catchment=cls.child_catchment)
        cls.grandchild_collection = Collection.objects.create(catchment=cls.grandchild_catchment)
        cls.unrelated_collection = Collection.objects.create(catchment=CollectionCatchment.objects.create())

    def test_downstream_collections_contains_collections_of_self(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.collection, collections)

    def test_downstream_collections_contains_collections_of_child_catchment(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.child_collection, collections)

    def test_downstream_collections_contains_collections_of_grandchild_catchment(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.grandchild_collection, collections)

    def test_downstream_collections_excludes_unrelated_collection(self):
        collections = self.catchment.downstream_collections
        self.assertNotIn(self.unrelated_collection, collections)

    def test_upstream_collections_includes_collections_from_all_ancestor_catchments(self):
        collections = self.great_grandchild_catchment.upstream_collections
        self.assertIn(self.collection, collections)
        self.assertIn(self.child_collection, collections)
        self.assertIn(self.grandchild_collection, collections)

    def test_get_absolute_url(self):
        self.assertEqual(
            reverse('collectioncatchment-detail', kwargs={'pk': self.catchment.pk}),
            self.collection.catchment.get_absolute_url()
        )


class WasteStreamQuerysetTestCase(TestCase):

    def setUp(self):
        self.allowed_material_1 = Material.objects.create(name='Allowed Material 1')
        self.allowed_material_2 = Material.objects.create(name='Allowed Material 2')
        self.forbidden_material_1 = Material.objects.create(name='Forbidden Material 1')
        self.forbidden_material_2 = Material.objects.create(name='Forbidden Material 2')
        self.unrelated_material = Material.objects.create(name='Unrelated Material')
        self.category = WasteCategory.objects.create(name='Biowaste')
        self.waste_stream = WasteStream.objects.create(name='Waste Stream 1', category=self.category)
        self.waste_stream.allowed_materials.add(self.allowed_material_1)
        self.waste_stream.allowed_materials.add(self.allowed_material_2)
        self.waste_stream.forbidden_materials.add(self.forbidden_material_1)
        self.waste_stream.forbidden_materials.add(self.forbidden_material_2)
        self.waste_stream_2 = WasteStream.objects.create(name='Waste Stream 2', category=self.category)
        self.waste_stream_2.allowed_materials.add(self.allowed_material_1)
        self.waste_stream_2.forbidden_materials.add(self.forbidden_material_1)

    def test_match_allowed_materials_returns_all_waste_streams_with_all_given_allowed_materials(self):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        self.assertQuerysetEqual(
            WasteStream.objects.filter(id=self.waste_stream.id).order_by('id'),
            WasteStream.objects.match_allowed_materials(allowed_materials).order_by('id')
        )

    def test_match_forbidden_materials_returns_all_waste_streams_with_all_given_forbidden_materials(self):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        self.assertQuerysetEqual(
            WasteStream.objects.filter(id=self.waste_stream.id).order_by('id'),
            WasteStream.objects.match_forbidden_materials(forbidden_materials).order_by('id')
        )

    def test_get_or_create_finds_existing_waste_stream_by_given_name_and_category(self):
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=self.waste_stream.name
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream),
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_finds_existing_waste_stream_with_given_allowed_materials(self):
        allowed_materials = Material.objects.filter(id__in=[self.allowed_material_1.id, self.allowed_material_2.id])
        instance, created = WasteStream.objects.get_or_create(
            name='Waste Stream 1',
            category=self.category,
            allowed_materials=allowed_materials
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_finds_existing_waste_stream_with_given_forbidden_materials(self):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id])
        instance, created = WasteStream.objects.get_or_create(
            name='Waste Stream 1',
            category=self.category,
            forbidden_materials=forbidden_materials
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_finds_existing_waste_stream_with_given_combination_of_allowed_and_forbidden_materials(self):
        allowed_materials = Material.objects.filter(id__in=[self.allowed_material_1.id, self.allowed_material_2.id])
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id])
        instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_finds_existing_waste_stream_with_empty_queryset_of_allowed_materials(self):
        allowed_materials = Material.objects.none()
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id])
        created_instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials
        )
        self.assertTrue(created)
        self.assertFalse(created_instance.allowed_materials.exists())
        found_instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials
        )
        self.assertFalse(created)
        self.assertIsInstance(found_instance, WasteStream)
        self.assertDictEqual(comparable_model_dict(found_instance), comparable_model_dict(created_instance))

    def test_get_or_create_creates_new_wastestream_if_combination_of_allowed_materials_doesnt_exist(self):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id, self.unrelated_material.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials
        )
        self.assertTrue(created)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_creates_new_wastestream_if_combination_of_forbidden_materials_doesnt_exist(self):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id, self.unrelated_material.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            forbidden_materials=forbidden_materials
        )
        self.assertTrue(created)
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_get_or_create_creates_new_instance_without_allowed_materials_and_new_name(self):
        new_name = 'New waste stream'
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_get_or_create_creates_new_instance_with_allowed_materials_and_new_name(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
            allowed_materials=allowed_materials
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_creates_new_instance_with_forbidden_materials_and_new_name(self):
        new_name = 'New waste stream'
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
            forbidden_materials=forbidden_materials
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_get_or_create_creates_new_instance_with_combined_allowed_and_forbidden_materials_and_new_name(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_get_or_create_with_allowed_materials_in_defaults(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        defaults = {
            'category': self.category,
            'allowed_materials': allowed_materials
        }

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults,
            name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_with_forbidden_materials_in_defaults(self):
        new_name = 'New waste stream'
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        defaults = {
            'category': self.category,
            'forbidden_materials': forbidden_materials
        }

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults,
            name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_get_or_create_with_combined_allowed_and_forbidden_materials_in_defaults(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        defaults = {
            'category': self.category,
            'allowed_materials': allowed_materials,
            'forbidden_materials': forbidden_materials
        }

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults,
            name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_update_or_create_finds_existing_waste_stream_by_given_name_and_category_and_updates_new_name(self):
        new_name = 'New waste stream'

        instance, created = WasteStream.objects.update_or_create(
            defaults={'name': new_name},
            category=self.waste_stream.category,
            name=self.waste_stream.name
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_update_or_create_finds_existing_waste_stream_with_given_allowed_materials_and_updates_new_name(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={'name': new_name},
            category=self.waste_stream.category,
            allowed_materials=allowed_materials
        )

        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_finds_existing_waste_stream_with_given_forbidden_materials_and_updates_new_name(self):
        new_name = 'New waste stream'
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={'name': new_name},
            category=self.waste_stream.category,
            forbidden_materials=forbidden_materials
        )

        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_update_or_create_updates_altered_allowed_materials_with_given_id_and_category(self):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id, self.unrelated_material.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={'allowed_materials': allowed_materials},
            category=self.waste_stream.category,
            id=self.waste_stream.id
        )

        self.assertFalse(created)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_updates_altered_forbidden_materials_with_given_id_and_category(self):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id, self.unrelated_material.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={'forbidden_materials': forbidden_materials},
            category=self.waste_stream.category,
            id=self.waste_stream.id
        )

        self.assertFalse(created)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))

    def test_update_or_create_throws_validation_error_when_allowed_materials_not_unique(self):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id, self.unrelated_material.id]
        )

        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            allowed_materials=allowed_materials
        )
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))
        self.assertTrue(created)

        with self.assertRaises(ValidationError):
            WasteStream.objects.update_or_create(
                defaults={'allowed_materials': allowed_materials},
                id=self.waste_stream.id
            )

    def test_update_or_create_throws_validation_error_when_forbidden_materials_not_unique(self):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id, self.unrelated_material.id]
        )

        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            forbidden_materials=forbidden_materials
        )
        self.assertEqual(set(forbidden_materials), set(instance.forbidden_materials.all()))
        self.assertTrue(created)

        with self.assertRaises(ValidationError):
            WasteStream.objects.update_or_create(
                defaults={'forbidden_materials': forbidden_materials},
                id=self.waste_stream.id
            )


class WasteStreamTestCase(TestCase):

    def test_models_uses_manager_from_custom_waste_stream_queryset(self):
        self.assertEqual(
            type(WasteStream.objects).__name__,
            'ManagerFromWasteStreamQuerySet'
        )


class WasteFlyerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            WasteFlyer.objects.create(abbreviation='WasteFlyer007', url='https://www.super-test-flyer.org')

    def setUp(self):
        pass

    def test_new_instance_is_saved_with_type_waste_flyer(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(abbreviation='WasteFlyer002')
        self.assertEqual(flyer.type, 'waste_flyer')

    def test_str_returns_url(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.get(abbreviation='WasteFlyer007')
        self.assertEqual(flyer.__str__(), 'https://www.super-test-flyer.org')


class CollectionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        collection_system = CollectionSystem.objects.create(name='System')
        catchment = CollectionCatchment.objects.create(name='Catchment')
        category = WasteCategory.objects.create(name='Category')
        waste_stream = WasteStream.objects.create(category=category)
        cls.collection = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream,
            valid_from=date(2024, 1, 1)
        )

    def test_collection_is_named_automatically_on_creation(self):
        self.assertEqual('Catchment Category System 2024', self.collection.name)

    def test_collection_name_is_updated_on_model_update(self):
        self.collection.collection_system = CollectionSystem.objects.create(name='New System')
        self.collection.save()
        self.assertEqual('Catchment Category New System 2024', self.collection.name)

    def test_collection_name_is_updated_when_collection_system_model_is_changed(self):
        system = CollectionSystem.objects.get(name='System')
        system.name = 'Updated System'
        system.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment Category Updated System 2024', self.collection.name)

    def test_collection_name_is_updated_when_waste_stream_model_is_changed(self):
        waste_stream = WasteStream.objects.get(category__name='Category')
        category = WasteCategory.objects.create(name='New Category')
        waste_stream.category = category
        waste_stream.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment New Category System 2024', self.collection.name)

    def test_collection_name_is_updated_when_waste_category_model_is_changed(self):
        category = WasteCategory.objects.get(name='Category')
        category.name = 'Updated Category'
        category.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment Updated Category System 2024', self.collection.name)

    def test_collection_name_is_updated_when_catchment_model_is_changed(self):
        catchment = CollectionCatchment.objects.get(name='Catchment')
        catchment.name = 'Updated Catchment'
        catchment.save()
        self.collection.refresh_from_db()
        self.assertEqual('Updated Catchment Category System 2024', self.collection.name)

    def test_collection_name_is_updated_when_year_is_changed(self):
        self.collection.valid_from = date(2025, 1, 1)
        self.collection.save()
        self.assertEqual('Catchment Category System 2025', self.collection.name)

    def test_currently_valid_returns_collection_with_past_valid_from_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.currently_valid(), [self.collection])

    def test_currently_valid_does_not_return_collection_with_future_valid_from_date(self):
        self.collection.valid_from = date.today() + timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.currently_valid(), [])

    def test_currently_valid_returns_collection_with_valid_from_date_today(self):
        self.collection.valid_from = date.today()
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.currently_valid(), [self.collection])

    def test_currently_valid_returns_collection_with_future_valid_until_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = date.today() + timedelta(days=1)
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.currently_valid(), [self.collection])

    def test_currently_valid_does_not_return_collection_with_past_valid_until_date(self):
        self.collection.valid_from = date.today() - timedelta(days=2)
        self.collection.valid_until = date.today() - timedelta(days=1)
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.currently_valid(), [])

    def test_valid_on_returns_collection_with_past_valid_from_date(self):
        day = date(2023, 6, 30)
        self.collection.valid_from = day - timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_future_valid_from_date(self):
        day = date(2023, 6, 30)
        self.collection.valid_from = day + timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.valid_on(day), [])

    def test_valid_on_returns_collection_with_given_valid_from_date(self):
        day = date(2023, 6, 30)
        self.collection.valid_from = day
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_returns_collection_with_future_valid_until_date(self):
        day = date(2023, 6, 30)
        self.collection.valid_from = day - timedelta(days=1)
        self.collection.valid_until = day + timedelta(days=1)
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_past_valid_until_date(self):
        day = date(2023, 6, 30)
        self.collection.valid_from = day - timedelta(days=2)
        self.collection.valid_until = day - timedelta(days=1)
        self.collection.save()
        self.assertQuerysetEqual(Collection.objects.valid_on(day), [])


class CollectionSeasonTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.distribution = TemporalDistribution.objects.get(name='Months of the year')
        CollectionSeason.objects.get(
            distribution=cls.distribution,
            first_timestep=Timestep.objects.get(name='January'),
            last_timestep=Timestep.objects.get(name='December')
        )

    def test_get_queryset_only_returns_from_months_of_the_year_distribution(self):
        Period.objects.create(
            distribution=TemporalDistribution.objects.default(),
            first_timestep=Timestep.objects.default(),
            last_timestep=Timestep.objects.default()
        )
        self.assertQuerysetEqual(
            Period.objects.filter(distribution=self.distribution),
            CollectionSeason.objects.all()
        )


class CollectionFrequencyTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name='Months of the year')
        cls.january = Timestep.objects.get(name='January')
        cls.june = Timestep.objects.get(name='June')
        cls.july = Timestep.objects.get(name='July')
        cls.december = Timestep.objects.get(name='December')
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.december
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.june
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.july,
            last_timestep=cls.december
        )
        cls.not_seasonal = CollectionFrequency.objects.create(name='Non-Seasonal Test Frequency')
        CollectionCountOptions.objects.create(frequency=cls.not_seasonal, season=whole_year, standard=35, option_1=70)
        cls.seasonal = CollectionFrequency.objects.create(name='Seasonal Test Frequency')
        CollectionCountOptions.objects.create(frequency=cls.seasonal, season=first_half_year, standard=35)
        CollectionCountOptions.objects.create(frequency=cls.seasonal, season=second_half_year, standard=35)

    def test_seasonal_returns_true_for_seasonal_frequency_object(self):
        self.assertTrue(self.seasonal.seasonal)

    def test_seasonal_returns_false_for_non_seasonal_frequency_object(self):
        self.assertFalse(self.not_seasonal.seasonal)

    def test_has_options_returns_true_for_frequency_with_optional_collection_count(self):
        self.assertTrue(self.not_seasonal.has_options)

    def test_has_options_returns_false_for_frequency_without_optional_collection_count(self):
        self.assertFalse(self.seasonal.has_options)

    def test_collections_per_year_returns_correct_sum_of_standard_values_of_all_seasons(self):
        self.assertEqual(70, self.seasonal.collections_per_year)
        self.assertEqual(35, self.not_seasonal.collections_per_year)
