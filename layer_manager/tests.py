from django.db.models.query import QuerySet
from django.test import TestCase

from materials.models import BaseObjects
from .models import DistributionSet, DistributionShare, LayerAggregatedDistribution


class LayerAggregatedDistributionTestCase(TestCase):

    def setUp(self):
        self.component = BaseObjects.objects.get.base_component
        self.timestep = BaseObjects.objects.get.base_timestep
        self.distribution = BaseObjects.objects.get.base_distribution
        self.aggregated_distribution = LayerAggregatedDistribution.objects.create(
            name='Test distribution',
            distribution=self.distribution
        )
        self.distribution_set = DistributionSet.objects.create(
            aggregated_distribution=self.aggregated_distribution,
            component=self.component
        )
        self.share = DistributionShare.objects.create(
            timestep=self.timestep,
            distribution_set=self.distribution_set,
            average=1.23,
            standard_deviation=0.02
        )

    def test_shares(self):
        shares = self.aggregated_distribution.shares
        self.assertIsInstance(shares, QuerySet)
        self.assertEqual(shares.count(), 1)
        share = shares.first()
        self.assertEqual(share.average, 1.23)

    def test_components(self):
        components = self.aggregated_distribution.components
        self.assertIsInstance(components, QuerySet)
        self.assertEqual(components.count(), 1)
        component = components.first()
        self.assertEqual(component.name, self.component.name)

    def test_serialized(self):
        expected = [{'label': self.component.name, 'data': [self.share.average]}]
        self.assertListEqual(expected, self.aggregated_distribution.serialized)
