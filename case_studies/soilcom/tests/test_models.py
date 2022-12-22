from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from distributions.models import Period, TemporalDistribution, Timestep
from maps.models import GeoDataset, Region
from materials.models import Material
from users.models import get_default_owner
from ..models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency, CollectionSystem,
                      WasteStream, WasteCategory, WasteFlyer, CollectionSeason)


class InitialDataTestCase(TestCase):

    @staticmethod
    def test_household_biowaste_collection_dataset_is_initialized():
        GeoDataset.objects.get(
            owner=get_default_owner(),
            name='Household Biowaste Collection',
            model_name='WasteCollection',
            region=Region.objects.get(name='Europe (NUTS)')
        )


def comparable_model_dict(instance):
    """
    Removes '_state' so that two model instances can be compared by their __dict__ property.
    """
    return {k: v for k, v in instance.__dict__.items() if
            k not in ('_state', 'lastmodified_at', '_prefetched_objects_cache')}


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
        self.owner = User.objects.create(username='owner', password='very-secure!')
        self.material1 = Material.objects.create(
            owner=self.owner,
            name='Test material 1'
        )
        self.material2 = Material.objects.create(
            owner=self.owner,
            name='Test material 2'
        )
        self.material3 = Material.objects.create(
            owner=self.owner,
            name='Test material 3'
        )
        self.category = WasteCategory.objects.create(
            owner=self.owner,
            name='Biowaste'
        )
        self.waste_stream = WasteStream.objects.create(
            owner=self.owner,
            category=self.category
        )
        self.waste_stream.allowed_materials.add(self.material1)
        self.waste_stream.allowed_materials.add(self.material2)

    def test_create_waste_stream_routine(self):
        waste_stream = WasteStream.objects.create(
            owner=self.owner,
            category=self.category,
            name='Test waste stream'
        )
        waste_stream.allowed_materials.add(self.material1)
        waste_stream.allowed_materials.add(self.material2)
        self.assertEqual(len(waste_stream.allowed_materials.all()), 2)

    def test_get_or_create_with_passing_allowed_materials(self):
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id])
        instance, created = WasteStream.objects.get_or_create(
            owner=self.owner,
            category=self.category,
            allowed_materials=allowed_materials
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_with_non_existing_allowed_materials_queryset(self):
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id, self.material3.id])
        instance, created = WasteStream.objects.get_or_create(
            owner=self.owner,
            category=self.category,
            allowed_materials=allowed_materials
        )
        self.assertTrue(created)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_without_passing_allowed_materials(self):
        instance, created = WasteStream.objects.get_or_create(
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            name=self.waste_stream.name
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream),
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))

    def test_get_or_create_creates_new_instance_without_allowed_materials(self):
        new_name = 'New waste stream'

        instance, created = WasteStream.objects.get_or_create(
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            name=new_name,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_get_or_create_creates_new_instance_with_allowed_materials(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id])

        instance, created = WasteStream.objects.get_or_create(
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            name=new_name,
            allowed_materials=allowed_materials
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_with_allowed_materials_in_defaults(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id])

        defaults = {
            'owner': self.owner,
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

    def test_update_or_create_without_passing_allowed_materials(self):
        new_name = 'New waste stream'

        instance, created = WasteStream.objects.update_or_create(
            defaults={'name': new_name},
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            name=self.waste_stream.name
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_update_or_create_with_passing_allowed_materials(self):
        new_name = 'New waste stream'
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id])

        instance, created = WasteStream.objects.update_or_create(
            defaults={'name': new_name},
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            allowed_materials=allowed_materials
        )

        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_with_altered_allowed_materials(self):
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id, self.material3.id])

        instance, created = WasteStream.objects.update_or_create(
            defaults={'allowed_materials': allowed_materials},
            owner=self.waste_stream.owner,
            category=self.waste_stream.category,
            id=self.waste_stream.id
        )

        self.assertFalse(created)
        self.assertDictEqual(comparable_model_dict(instance), comparable_model_dict(self.waste_stream))
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_throws_validation_error_when_allowed_materials_not_unique(self):
        allowed_materials = Material.objects.filter(id__in=[self.material1.id, self.material2.id, self.material3.id])

        instance, created = WasteStream.objects.get_or_create(
            owner=self.waste_stream.owner,
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


class WasteFlyerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')

        WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer007',
            url='https://www.super-test-flyer.org'
        )

    def setUp(self):
        pass

    def test_new_instance_is_saved_with_type_waste_flyer(self):
        flyer = WasteFlyer.objects.create(owner=User.objects.first(), abbreviation='WasteFlyer002')
        self.assertEqual(flyer.type, 'waste_flyer')

    def test_str_returns_url(self):
        flyer = WasteFlyer.objects.get(abbreviation='WasteFlyer007')
        self.assertEqual(flyer.__str__(), 'https://www.super-test-flyer.org')


class CollectionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        collection_system = CollectionSystem.objects.create(owner=get_default_owner(), name='System')
        catchment = CollectionCatchment.objects.create(owner=get_default_owner(), name='Catchment')
        category = WasteCategory.objects.create(owner=get_default_owner(), name='Category')
        waste_stream = WasteStream.objects.create(owner=get_default_owner(), category=category)
        cls.collection = Collection.objects.create(
            owner=get_default_owner(),
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream
        )

    def test_collection_is_named_automatically_on_creation(self):
        self.assertEqual('Catchment Category System', self.collection.name)

    def test_collection_name_is_updated_on_model_update(self):
        self.collection.collection_system = CollectionSystem.objects.create(owner=get_default_owner(),
                                                                            name='New System')
        self.collection.save()
        self.assertEqual('Catchment Category New System', self.collection.name)

    def test_collection_name_is_updated_when_collection_system_model_is_changed(self):
        system = CollectionSystem.objects.get(name='System')
        system.name = 'Updated System'
        system.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment Category Updated System', self.collection.name)

    def test_collection_name_is_updated_when_waste_stream_model_is_changed(self):
        waste_stream = WasteStream.objects.get(category__name='Category')
        category = WasteCategory.objects.create(owner=get_default_owner(), name='New Category')
        waste_stream.category = category
        waste_stream.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment New Category System', self.collection.name)

    def test_collection_name_is_updated_when_waste_category_model_is_changed(self):
        category = WasteCategory.objects.get(name='Category')
        category.name = 'Updated Category'
        category.save()
        self.collection.refresh_from_db()
        self.assertEqual('Catchment Updated Category System', self.collection.name)

    def test_collection_name_is_updated_when_catchment_model_is_changed(self):
        catchment = CollectionCatchment.objects.get(name='Catchment')
        catchment.name = 'Updated Catchment'
        catchment.save()
        self.collection.refresh_from_db()
        self.assertEqual('Updated Catchment Category System', self.collection.name)


class CollectionSeasonTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.distribution = TemporalDistribution.objects.get(name='Months of the year')
        CollectionSeason.objects.create(
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
