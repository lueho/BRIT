from django.test import TestCase

from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
from sources.roadside_trees.models import HamburgRoadsideTrees


class RoadsideTreeFilterTestCase(TestCase):
    def test_filter_form_has_no_form_tag(self):
        filtr = HamburgRoadsideTreesFilterSet(queryset=HamburgRoadsideTrees.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
