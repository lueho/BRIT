from django.apps import apps
from django.test import TestCase

from utils.object_management.models import get_default_owner


class UtilsInitialDataTestCase(TestCase):
    def test_no_unit_exists_for_default_owner(self):
        Unit = apps.get_model("properties", "Unit")
        owner = get_default_owner()
        unit = Unit.objects.get(owner=owner, name="No unit")
        self.assertTrue(unit.dimensionless)
