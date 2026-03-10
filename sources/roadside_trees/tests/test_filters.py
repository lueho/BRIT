from django.test import TestCase

from ..filters import HamburgRoadsideTreesFilterSet
from ..models import HamburgRoadsideTrees


class TreeFilterTestCase(TestCase):

    def test_filter_form_has_no_form_tag(self):
        filtr = HamburgRoadsideTreesFilterSet(queryset=HamburgRoadsideTrees.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
