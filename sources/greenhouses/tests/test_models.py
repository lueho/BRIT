"""Tests for sources.greenhouses.models."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Culture, Greenhouse, GreenhouseGrowthCycle


class GreenhouseGroupedGrowthCyclesTestCase(TestCase):
    """Test Greenhouse.grouped_growth_cycles does not raise AttributeError."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="gh_test_user")
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner,
            name="Test Greenhouse",
        )
        cls.culture = Culture.objects.create(
            name="Tomato",
            owner=cls.owner,
            publication_status="published",
        )
        cls.cycle = GreenhouseGrowthCycle.objects.create(
            owner=cls.owner,
            greenhouse=cls.greenhouse,
            culture=cls.culture,
            cycle_number=1,
        )

    def test_grouped_growth_cycles_returns_dict_keyed_by_culture(self):
        """grouped_growth_cycles should group by culture, not a missing 'material' attr."""
        result = self.greenhouse.grouped_growth_cycles()
        self.assertIn(1, result)
        self.assertIn(self.culture, result[1])
        self.assertEqual(result[1][self.culture], [self.cycle])
