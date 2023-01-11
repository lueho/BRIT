from django.test import TestCase

from ..filters import CatchmentFilter
from ..models import Catchment


class CatchmentFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.catchment_1 = Catchment.objects.create(name='Catchment 1')

    def test_filter_valid_on_valid_input(self):
        data = {'name': 'Catchment'}
        filtr = CatchmentFilter(data, queryset=Catchment.objects.all())
        form = filtr.form
        self.assertTrue(form.is_valid())
        self.assertQuerysetEqual(Catchment.objects.all(), filtr.qs)

    def test_filter_form_has_no_formtags(self):
        filtr = CatchmentFilter(queryset=Catchment.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
