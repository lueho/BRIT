from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from case_studies.soilcom.models import WasteStream, WasteCategory
from materials.models import Material


def comparable_model_dict(instance):
    """
    Removes '_state' so that two model instances can be compared by their __dict__ property.
    """
    return {k: v for k, v in instance.__dict__.items() if
            k not in ('_state', 'lastmodified_at', '_prefetched_objects_cache')}


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
