from django.test import TestCase

from ..filters import CatchmentFilterSet
from ..models import Catchment


class CatchmentFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.catchment_1 = Catchment.objects.create(name='Catchment 1')

    def test_filter_valid_on_valid_input(self):
        data = {'name': 'Catchment'}
        filtr = CatchmentFilterSet(data, queryset=Catchment.objects.all())
        form = filtr.form
        self.assertTrue(form.is_valid())
        self.assertQuerySetEqual(Catchment.objects.all(), filtr.qs)

    def test_filter_form_has_no_formtags(self):
        filtr = CatchmentFilterSet(queryset=Catchment.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
