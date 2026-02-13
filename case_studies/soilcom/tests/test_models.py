from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from distributions.models import Period, TemporalDistribution, Timestep
from materials.models import Material
from utils.tests.testcases import comparable_model_dict

from ..models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
    CollectionSystem,
    WasteCategory,
    WasteFlyer,
    WasteStream,
)


class InitialDataTestCase(TestCase):
    @staticmethod
    def test_simple_initial_collection_frequency_exists():
        season = CollectionSeason.objects.get(
            distribution=TemporalDistribution.objects.get(name="Months of the year"),
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )
        CollectionCountOptions.objects.get(
            frequency__type="Fixed", season=season, standard=52
        )


class CollectionCatchmentTestCase(TestCase):
    catchment = None

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="Test Catchment")
        cls.child_catchment = CollectionCatchment.objects.create(parent=cls.catchment)
        cls.grandchild_catchment = CollectionCatchment.objects.create(
            parent=cls.child_catchment
        )
        cls.great_grandchild_catchment = CollectionCatchment.objects.create(
            parent=cls.grandchild_catchment
        )
        cls.collection = Collection.objects.create(catchment=cls.catchment)
        cls.child_collection = Collection.objects.create(catchment=cls.child_catchment)
        cls.grandchild_collection = Collection.objects.create(
            catchment=cls.grandchild_catchment
        )
        cls.unrelated_collection = Collection.objects.create(
            catchment=CollectionCatchment.objects.create()
        )

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

    def test_upstream_collections_includes_collections_from_all_ancestor_catchments(
        self,
    ):
        collections = self.great_grandchild_catchment.upstream_collections
        self.assertIn(self.collection, collections)
        self.assertIn(self.child_collection, collections)
        self.assertIn(self.grandchild_collection, collections)

    def test_get_absolute_url(self):
        self.assertEqual(
            reverse("collectioncatchment-detail", kwargs={"pk": self.catchment.pk}),
            self.collection.catchment.get_absolute_url(),
        )


class WasteStreamQuerysetTestCase(TestCase):
    def setUp(self):
        self.allowed_material_1 = Material.objects.create(name="Allowed Material 1")
        self.allowed_material_2 = Material.objects.create(name="Allowed Material 2")
        self.forbidden_material_1 = Material.objects.create(name="Forbidden Material 1")
        self.forbidden_material_2 = Material.objects.create(name="Forbidden Material 2")
        self.unrelated_material = Material.objects.create(name="Unrelated Material")
        self.category = WasteCategory.objects.create(name="Biowaste")
        self.waste_stream = WasteStream.objects.create(
            name="Waste Stream 1", category=self.category
        )
        self.waste_stream.allowed_materials.add(self.allowed_material_1)
        self.waste_stream.allowed_materials.add(self.allowed_material_2)
        self.waste_stream.forbidden_materials.add(self.forbidden_material_1)
        self.waste_stream.forbidden_materials.add(self.forbidden_material_2)
        self.waste_stream_2 = WasteStream.objects.create(
            name="Waste Stream 2", category=self.category
        )
        self.waste_stream_2.allowed_materials.add(self.allowed_material_1)
        self.waste_stream_2.forbidden_materials.add(self.forbidden_material_1)

    def test_match_allowed_materials_returns_all_waste_streams_with_all_given_allowed_materials(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        self.assertQuerySetEqual(
            WasteStream.objects.filter(id=self.waste_stream.id).order_by("id"),
            WasteStream.objects.match_allowed_materials(allowed_materials).order_by(
                "id"
            ),
        )

    def test_match_forbidden_materials_returns_all_waste_streams_with_all_given_forbidden_materials(
        self,
    ):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        self.assertQuerySetEqual(
            WasteStream.objects.filter(id=self.waste_stream.id).order_by("id"),
            WasteStream.objects.match_forbidden_materials(forbidden_materials).order_by(
                "id"
            ),
        )

    def test_get_or_create_finds_existing_waste_stream_by_given_name_and_category(self):
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category, name=self.waste_stream.name
        )
        self.assertFalse(created)
        (self.assertIsInstance(instance, WasteStream),)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )

    def test_get_or_create_finds_existing_waste_stream_with_given_allowed_materials(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            name="Waste Stream 1",
            category=self.category,
            allowed_materials=allowed_materials,
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )

    def test_get_or_create_finds_existing_waste_stream_with_given_forbidden_materials(
        self,
    ):
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            name="Waste Stream 1",
            category=self.category,
            forbidden_materials=forbidden_materials,
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )

    def test_get_or_create_finds_existing_waste_stream_with_given_combination_of_allowed_and_forbidden_materials(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials,
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )

    def test_get_or_create_finds_existing_waste_stream_with_empty_queryset_of_allowed_materials(
        self,
    ):
        allowed_materials = Material.objects.none()
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        created_instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials,
        )
        self.assertTrue(created)
        self.assertFalse(created_instance.allowed_materials.exists())
        found_instance, created = WasteStream.objects.get_or_create(
            category=self.category,
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials,
        )
        self.assertFalse(created)
        self.assertIsInstance(found_instance, WasteStream)
        self.assertDictEqual(
            comparable_model_dict(found_instance),
            comparable_model_dict(created_instance),
        )

    def test_get_or_create_creates_new_wastestream_if_combination_of_allowed_materials_doesnt_exist(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[
                self.allowed_material_1.id,
                self.allowed_material_2.id,
                self.unrelated_material.id,
            ]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.category, allowed_materials=allowed_materials
        )
        self.assertTrue(created)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_creates_new_wastestream_if_combination_of_forbidden_materials_doesnt_exist(
        self,
    ):
        forbidden_materials = Material.objects.filter(
            id__in=[
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
                self.unrelated_material.id,
            ]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.category, forbidden_materials=forbidden_materials
        )
        self.assertTrue(created)
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_get_or_create_creates_new_instance_without_allowed_materials_and_new_name(
        self,
    ):
        new_name = "New waste stream"
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_get_or_create_creates_new_instance_with_allowed_materials_and_new_name(
        self,
    ):
        new_name = "New waste stream"
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
            allowed_materials=allowed_materials,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_creates_new_instance_with_forbidden_materials_and_new_name(
        self,
    ):
        new_name = "New waste stream"
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )
        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category,
            name=new_name,
            forbidden_materials=forbidden_materials,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_get_or_create_creates_new_instance_with_combined_allowed_and_forbidden_materials_and_new_name(
        self,
    ):
        new_name = "New waste stream"
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
            forbidden_materials=forbidden_materials,
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_get_or_create_with_allowed_materials_in_defaults(self):
        new_name = "New waste stream"
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        defaults = {"category": self.category, "allowed_materials": allowed_materials}

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults, name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_get_or_create_with_forbidden_materials_in_defaults(self):
        new_name = "New waste stream"
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        defaults = {
            "category": self.category,
            "forbidden_materials": forbidden_materials,
        }

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults, name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_get_or_create_with_combined_allowed_and_forbidden_materials_in_defaults(
        self,
    ):
        new_name = "New waste stream"
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        defaults = {
            "category": self.category,
            "allowed_materials": allowed_materials,
            "forbidden_materials": forbidden_materials,
        }

        instance, created = WasteStream.objects.get_or_create(
            defaults=defaults, name=new_name
        )
        self.assertTrue(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_update_or_create_finds_existing_waste_stream_by_given_name_and_category_and_updates_new_name(
        self,
    ):
        new_name = "New waste stream"

        instance, created = WasteStream.objects.update_or_create(
            defaults={"name": new_name},
            category=self.waste_stream.category,
            name=self.waste_stream.name,
        )
        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)

    def test_update_or_create_finds_existing_waste_stream_with_given_allowed_materials_and_updates_new_name(
        self,
    ):
        new_name = "New waste stream"
        allowed_materials = Material.objects.filter(
            id__in=[self.allowed_material_1.id, self.allowed_material_2.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={"name": new_name},
            category=self.waste_stream.category,
            allowed_materials=allowed_materials,
        )

        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_finds_existing_waste_stream_with_given_forbidden_materials_and_updates_new_name(
        self,
    ):
        new_name = "New waste stream"
        forbidden_materials = Material.objects.filter(
            id__in=[self.forbidden_material_1.id, self.forbidden_material_2.id]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={"name": new_name},
            category=self.waste_stream.category,
            forbidden_materials=forbidden_materials,
        )

        self.assertFalse(created)
        self.assertIsInstance(instance, WasteStream)
        self.assertEqual(instance.name, new_name)
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_update_or_create_updates_altered_allowed_materials_with_given_id_and_category(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[
                self.allowed_material_1.id,
                self.allowed_material_2.id,
                self.unrelated_material.id,
            ]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={"allowed_materials": allowed_materials},
            category=self.waste_stream.category,
            id=self.waste_stream.id,
        )

        self.assertFalse(created)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))

    def test_update_or_create_updates_altered_forbidden_materials_with_given_id_and_category(
        self,
    ):
        forbidden_materials = Material.objects.filter(
            id__in=[
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
                self.unrelated_material.id,
            ]
        )

        instance, created = WasteStream.objects.update_or_create(
            defaults={"forbidden_materials": forbidden_materials},
            category=self.waste_stream.category,
            id=self.waste_stream.id,
        )

        self.assertFalse(created)
        self.assertDictEqual(
            comparable_model_dict(instance), comparable_model_dict(self.waste_stream)
        )
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )

    def test_update_or_create_throws_validation_error_when_allowed_materials_not_unique(
        self,
    ):
        allowed_materials = Material.objects.filter(
            id__in=[
                self.allowed_material_1.id,
                self.allowed_material_2.id,
                self.unrelated_material.id,
            ]
        )

        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category, allowed_materials=allowed_materials
        )
        self.assertEqual(set(allowed_materials), set(instance.allowed_materials.all()))
        self.assertTrue(created)

        with self.assertRaises(ValidationError):
            WasteStream.objects.update_or_create(
                defaults={"allowed_materials": allowed_materials},
                id=self.waste_stream.id,
            )

    def test_update_or_create_throws_validation_error_when_forbidden_materials_not_unique(
        self,
    ):
        forbidden_materials = Material.objects.filter(
            id__in=[
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
                self.unrelated_material.id,
            ]
        )

        instance, created = WasteStream.objects.get_or_create(
            category=self.waste_stream.category, forbidden_materials=forbidden_materials
        )
        self.assertEqual(
            set(forbidden_materials), set(instance.forbidden_materials.all())
        )
        self.assertTrue(created)

        with self.assertRaises(ValidationError):
            WasteStream.objects.update_or_create(
                defaults={"forbidden_materials": forbidden_materials},
                id=self.waste_stream.id,
            )


class WasteStreamMaterialIdsTestCase(TestCase):
    """Tests for WasteStreamQuerySet._material_ids helper method."""

    def setUp(self):
        self.material_1 = Material.objects.create(name="Material 1")
        self.material_2 = Material.objects.create(name="Material 2")

    def test_material_ids_with_none_returns_none(self):
        """Verify _material_ids returns None when input is None."""
        from ..models import WasteStreamQuerySet

        result = WasteStreamQuerySet._material_ids(None)
        self.assertIsNone(result)

    def test_material_ids_with_empty_queryset_returns_empty_list(self):
        """Verify _material_ids returns empty list for empty queryset."""
        from ..models import WasteStreamQuerySet

        empty_qs = Material.objects.none()
        result = WasteStreamQuerySet._material_ids(empty_qs)
        self.assertEqual(result, [])

    def test_material_ids_with_queryset_returns_id_list(self):
        """Verify _material_ids extracts IDs from queryset."""
        from ..models import WasteStreamQuerySet

        qs = Material.objects.filter(id__in=[self.material_1.id, self.material_2.id])
        result = WasteStreamQuerySet._material_ids(qs)
        self.assertEqual(
            sorted(result), sorted([self.material_1.id, self.material_2.id])
        )

    def test_material_ids_with_list_of_ids_returns_same_list(self):
        """Verify _material_ids returns the same list when given list of IDs."""
        from ..models import WasteStreamQuerySet

        id_list = [self.material_1.id, self.material_2.id]
        result = WasteStreamQuerySet._material_ids(id_list)
        self.assertEqual(result, id_list)

    def test_material_ids_with_empty_list_returns_empty_list(self):
        """Verify _material_ids returns empty list when given empty list."""
        from ..models import WasteStreamQuerySet

        result = WasteStreamQuerySet._material_ids([])
        self.assertEqual(result, [])

    def test_get_or_create_accepts_list_of_ids_for_allowed_materials(self):
        """Verify get_or_create works with list of IDs for allowed_materials."""
        category = WasteCategory.objects.create(name="Test Category")
        id_list = [self.material_1.id, self.material_2.id]

        instance, created = WasteStream.objects.get_or_create(
            category=category,
            allowed_materials=id_list,
        )
        self.assertTrue(created)
        self.assertEqual(
            set(instance.allowed_materials.values_list("id", flat=True)),
            set(id_list),
        )

        # Second call should find the existing instance
        instance2, created2 = WasteStream.objects.get_or_create(
            category=category,
            allowed_materials=id_list,
        )
        self.assertFalse(created2)
        self.assertEqual(instance.pk, instance2.pk)

    def test_get_or_create_accepts_list_of_ids_for_forbidden_materials(self):
        """Verify get_or_create works with list of IDs for forbidden_materials."""
        category = WasteCategory.objects.create(name="Test Category 2")
        id_list = [self.material_1.id, self.material_2.id]

        instance, created = WasteStream.objects.get_or_create(
            category=category,
            forbidden_materials=id_list,
        )
        self.assertTrue(created)
        self.assertEqual(
            set(instance.forbidden_materials.values_list("id", flat=True)),
            set(id_list),
        )

        # Second call should find the existing instance
        instance2, created2 = WasteStream.objects.get_or_create(
            category=category,
            forbidden_materials=id_list,
        )
        self.assertFalse(created2)
        self.assertEqual(instance.pk, instance2.pk)


class WasteStreamTestCase(TestCase):
    def test_models_uses_manager_from_custom_waste_stream_queryset(self):
        self.assertEqual(
            type(WasteStream.objects).__name__, "ManagerFromWasteStreamQuerySet"
        )


class WasteFlyerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            WasteFlyer.objects.create(
                abbreviation="WasteFlyer007", url="https://www.super-test-flyer.org"
            )

    def setUp(self):
        pass

    def test_new_instance_is_saved_with_type_waste_flyer(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(abbreviation="WasteFlyer002")
        self.assertEqual(flyer.type, "waste_flyer")

    def test_str_returns_url(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.get(abbreviation="WasteFlyer007")
        self.assertEqual(flyer.__str__(), "https://www.super-test-flyer.org")


class CollectionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        collection_system = CollectionSystem.objects.create(name="System")
        catchment = CollectionCatchment.objects.create(name="Catchment")
        category = WasteCategory.objects.create(name="Category")
        waste_stream = WasteStream.objects.create(category=category)
        cls.predecessor_collection = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream,
            valid_from=date(2023, 1, 1),
            valid_until=date(2023, 12, 31),
            description="Predecessor Collection",
        )
        cls.collection = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream,
            valid_from=date(2024, 1, 1),
            description="Current Collection",
        )

    def test_collection_is_named_automatically_on_creation(self):
        self.assertEqual("Catchment Category System 2024", self.collection.name)

    def test_collection_name_is_updated_on_model_update(self):
        self.collection.collection_system = CollectionSystem.objects.create(
            name="New System"
        )
        self.collection.save()
        self.assertEqual("Catchment Category New System 2024", self.collection.name)

    def test_collection_name_is_updated_when_collection_system_model_is_changed(self):
        system = CollectionSystem.objects.get(name="System")
        system.name = "Updated System"
        system.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment Category Updated System 2024", self.collection.name)

    def test_collection_name_is_updated_when_waste_stream_model_is_changed(self):
        waste_stream = WasteStream.objects.get(category__name="Category")
        category = WasteCategory.objects.create(name="New Category")
        waste_stream.category = category
        waste_stream.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment New Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_waste_category_model_is_changed(self):
        category = WasteCategory.objects.get(name="Category")
        category.name = "Updated Category"
        category.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment Updated Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_catchment_model_is_changed(self):
        catchment = CollectionCatchment.objects.get(name="Catchment")
        catchment.name = "Updated Catchment"
        catchment.save()
        self.collection.refresh_from_db()
        self.assertEqual("Updated Catchment Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_year_is_changed(self):
        self.collection.valid_from = date(2025, 1, 1)
        self.collection.save()
        self.assertEqual("Catchment Category System 2025", self.collection.name)

    def test_currently_valid_returns_collection_with_past_valid_from_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_does_not_return_collection_with_future_valid_from_date(
        self,
    ):
        self.collection.valid_from = date.today() + timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.currently_valid(), [])

    def test_currently_valid_returns_collection_with_valid_from_date_today(self):
        self.collection.valid_from = date.today()
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_returns_collection_with_future_valid_until_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = date.today() + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_does_not_return_collection_with_past_valid_until_date(
        self,
    ):
        self.collection.valid_from = date.today() - timedelta(days=2)
        self.collection.valid_until = date.today() - timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.currently_valid(), [])

    def test_archived_returns_collection_with_past_valid_until_date(self):
        self.collection.valid_from = date.today()
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.archived(), [self.predecessor_collection]
        )

    def test_archived_does_not_return_collection_with_future_valid_until_date(self):
        self.collection.valid_from = date.today() + timedelta(days=2)
        self.collection.save()
        self.predecessor_collection.valid_until = date.today() + timedelta(days=1)
        self.predecessor_collection.save()
        self.assertQuerySetEqual(Collection.objects.archived(), [])

    def test_archived_returns_collection_with_valid_until_date_today(self):
        self.collection.valid_from = date.today() + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.archived(), [self.predecessor_collection]
        )

    def test_valid_on_returns_collection_with_past_valid_from_date(self):
        day = date(2024, 6, 30)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_future_valid_from_date(self):
        day = date(2022, 6, 30)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [])

    def test_valid_on_returns_collection_with_given_valid_from_date(self):
        day = date(2024, 1, 1)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_returns_collection_with_future_valid_until_date(self):
        day = date(2024, 6, 30)
        self.collection.valid_until = day + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_past_valid_until_date(self):
        day = date(2024, 6, 30)
        self.collection.valid_until = day - timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [])

    def test_predecessor_returns_predecessor_collection(self):
        self.collection.predecessors.add(self.predecessor_collection)
        self.assertEqual(
            self.predecessor_collection, self.collection.predecessors.first()
        )

    def test_successor_returns_successor_collection(self):
        self.collection.predecessors.add(self.predecessor_collection)
        self.assertEqual(
            self.collection, self.predecessor_collection.successors.first()
        )

    def test_valid_until_cannot_be_before_valid_from(self):
        self.collection.valid_until = date(2023, 12, 31)
        with self.assertRaises(ValidationError):
            self.collection.full_clean()
            self.collection.save()


class CollectionVersioningHelpersTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)

    def _mk(self, year):
        return Collection.objects.create(
            catchment=self.catchment,
            collection_system=self.system,
            waste_stream=self.stream,
            valid_from=date(year, 1, 1),
        )

    def test_all_versions_and_anchor_linear_chain(self):
        a = self._mk(2020)
        b = self._mk(2021)
        c = self._mk(2022)
        b.predecessors.add(a)
        c.predecessors.add(b)

        self.assertSetEqual(a.version_chain_ids, {a.pk, b.pk, c.pk})
        self.assertSetEqual(
            set(b.all_versions().values_list("pk", flat=True)), {a.pk, b.pk, c.pk}
        )
        self.assertEqual(c.version_anchor, a)

    def test_version_anchor_in_cycle_falls_back_to_earliest(self):
        a = self._mk(2020)
        b = self._mk(2019)
        # Create a cycle: a<->b
        a.predecessors.add(b)
        b.predecessors.add(a)

        # No node without predecessors; should pick earliest by valid_from then pk
        anchor = a.version_anchor
        self.assertIn(anchor.pk, {a.pk, b.pk})
        self.assertEqual(anchor.valid_from, min(a.valid_from, b.valid_from))


class CollectionStatisticsAccessorsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.root = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        cls.succ = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.succ.predecessors.add(cls.root)

    def test_collectionpropertyvalues_for_display_dedup_and_scope(self):
        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="P", publication_status="published")
        unit = Unit.objects.create(name="U", publication_status="published")
        # Two values for same (prop, unit, year) across chain
        CollectionPropertyValue.objects.create(
            collection=self.root,
            property=prop,
            unit=unit,
            year=2020,
            average=10,
            publication_status="private",
        )
        v_succ = CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2020,
            average=11,
            publication_status="published",
        )

        # Anonymous: only published, dedup keeps published one
        anon_list = self.succ.collectionpropertyvalues_for_display(user=None)
        self.assertEqual(len(anon_list), 1)
        self.assertEqual(anon_list[0].pk, v_succ.pk)

        # Owner-like visibility: simulate staff/owner by passing a dummy user with is_staff=True
        class U:
            is_staff = True
            is_authenticated = True

        full_list = self.succ.collectionpropertyvalues_for_display(user=U())
        self.assertEqual(len(full_list), 1)  # dedup keeps published due to ordering
        self.assertEqual(full_list[0].pk, v_succ.pk)

    def test_aggregatedcollectionpropertyvalues_for_display_chain_and_scope(self):
        from case_studies.soilcom.models import AggregatedCollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="PA", publication_status="published")
        unit = Unit.objects.create(name="UA", publication_status="published")

        agg1 = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2020,
            average=42,
            publication_status="private",
        )
        agg1.collections.add(self.root)

        agg2 = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2021,
            average=43,
            publication_status="published",
        )
        agg2.collections.add(self.succ)

        # Anonymous sees only published
        anon = self.root.aggregatedcollectionpropertyvalues_for_display(user=None)
        self.assertEqual([a.year for a in anon], [2021])

        # Staff sees both, order by (property, unit, year, publication_order, -created_at, -pk)
        class U:
            is_staff = True
            is_authenticated = True

        both = self.succ.aggregatedcollectionpropertyvalues_for_display(user=U())
        self.assertEqual({a.year for a in both}, {2020, 2021})

    def test_collectionpropertyvalues_for_display_published_tie_prefers_latest_version(
        self,
    ):
        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="TP", publication_status="published")
        unit = Unit.objects.create(name="TU", publication_status="published")

        CollectionPropertyValue.objects.create(
            collection=self.root,
            property=prop,
            unit=unit,
            year=2022,
            average=1,
            publication_status="published",
        )
        v_succ = CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2022,
            average=2,
            publication_status="published",
        )

        lst = self.root.collectionpropertyvalues_for_display(user=None)
        filtered = [
            v
            for v in lst
            if v.property_id == prop.pk and v.unit_id == unit.pk and v.year == 2022
        ]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].pk, v_succ.pk)

    def test_collectionpropertyvalues_for_display_prefetches_owner(self):
        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="QOwner", publication_status="published")
        unit = Unit.objects.create(name="QUnit", publication_status="published")
        CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2023,
            average=3.14,
            publication_status="published",
        )

        cpvs = self.succ.collectionpropertyvalues_for_display(user=None)

        with self.assertNumQueries(0):
            _ = [value.owner.username for value in cpvs]

    def test_aggregatedcollectionpropertyvalues_for_display_prefetches_owner(self):
        from case_studies.soilcom.models import AggregatedCollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="AQOwner", publication_status="published")
        unit = Unit.objects.create(name="AQUnit", publication_status="published")
        aggregated = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2024,
            average=2.71,
            publication_status="published",
        )
        aggregated.collections.add(self.succ)

        values = self.succ.aggregatedcollectionpropertyvalues_for_display(user=None)

        with self.assertNumQueries(0):
            _ = [value.owner.username for value in values]


class CollectionSeasonTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        CollectionSeason.objects.get(
            distribution=cls.distribution,
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )

    def test_get_queryset_only_returns_from_months_of_the_year_distribution(self):
        self.assertQuerySetEqual(
            Period.objects.filter(distribution=self.distribution),
            CollectionSeason.objects.all(),
        )


class CollectionFrequencyTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(name="January")
        cls.june = Timestep.objects.get(name="June")
        cls.july = Timestep.objects.get(name="July")
        cls.december = Timestep.objects.get(name="December")
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.december,
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.june,
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.july,
            last_timestep=cls.december,
        )
        cls.not_seasonal = CollectionFrequency.objects.create(
            name="Non-Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.not_seasonal, season=whole_year, standard=35, option_1=70
        )
        cls.seasonal = CollectionFrequency.objects.create(
            name="Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal, season=first_half_year, standard=35
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal, season=second_half_year, standard=35
        )

    def test_seasonal_returns_true_for_seasonal_frequency_object(self):
        self.assertTrue(self.seasonal.seasonal)

    def test_seasonal_returns_false_for_non_seasonal_frequency_object(self):
        self.assertFalse(self.not_seasonal.seasonal)

    def test_has_options_returns_true_for_frequency_with_optional_collection_count(
        self,
    ):
        self.assertTrue(self.not_seasonal.has_options)

    def test_has_options_returns_false_for_frequency_without_optional_collection_count(
        self,
    ):
        self.assertFalse(self.seasonal.has_options)

    def test_collections_per_year_returns_correct_sum_of_standard_values_of_all_seasons(
        self,
    ):
        self.assertEqual(70, self.seasonal.collections_per_year)
        self.assertEqual(35, self.not_seasonal.collections_per_year)
