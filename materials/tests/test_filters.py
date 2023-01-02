from django.test import TestCase

from ..filters import SampleFilter
from ..models import Sample


class SampleFilterTestCase(TestCase):

    def test_filter_form_has_no_formtags(self):
        filtr = SampleFilter(queryset=Sample.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
