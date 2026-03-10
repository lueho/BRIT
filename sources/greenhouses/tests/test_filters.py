from django.test import TestCase

from ..filters import GreenhouseFilter
from ..models import NantesGreenhouses


class GreenhouseFilterTestCase(TestCase):

    def test_filter_form_has_no_formtags(self):
        filtr = GreenhouseFilter(queryset=NantesGreenhouses.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
