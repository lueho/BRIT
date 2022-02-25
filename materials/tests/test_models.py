from django.test import TestCase

from ..models import MaterialComponentGroup, MaterialComponent


class InitialDataTestCase(TestCase):

    def test_base_component_group_is_created_from_migrations(self):
        MaterialComponentGroup.objects.get(name='Total Material')
        self.assertEqual(MaterialComponentGroup.objects.all().count(), 1)

    def test_base_component_is_created_from_migrations(self):
        MaterialComponent.objects.get(name='Fresh Matter (FM)')
        self.assertEqual(MaterialComponent.objects.all().count(), 1)


class MaterialComponentGroupTestCase(TestCase):

    def test_get_default_material_component_group(self):
        default = MaterialComponentGroup.objects.default()
        self.assertIsInstance(default, MaterialComponentGroup)
        self.assertEqual(default.name, 'Total Material')


class MaterialComponentTestCase(TestCase):

    def test_get_default_material_component(self):
        default = MaterialComponent.objects.default()
        self.assertIsInstance(default, MaterialComponent)
        self.assertEqual(default.name, 'Fresh Matter (FM)')
