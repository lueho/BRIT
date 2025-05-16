from django.apps import apps

from users.utils import get_default_owner


from django.test import TestCase

class UtilsInitialDataTestCase(TestCase):
    def test_no_unit_exists_for_default_owner(self):
        Unit = apps.get_model('properties', 'Unit')
        owner = get_default_owner()
        unit = Unit.objects.get(owner=owner, name='No unit')
        self.assertTrue(unit.dimensionless)
