from django.db.models.query import QuerySet
from django.test import TestCase

from distributions.models import Timestep, TemporalDistribution
from layer_manager.models import DistributionSet, DistributionShare, LayerAggregatedDistribution
from materials.models import MaterialComponent


class LayerAggregatedDistributionTestCase(TestCase):

    def setUp(self):
        self.component = MaterialComponent.objects.default()
        self.timestep = Timestep.objects.default()
        self.distribution = TemporalDistribution.objects.default()
        self.aggregated_distribution = LayerAggregatedDistribution.objects.create(
            name='Test distribution',
            distribution=self.distribution
        )
        self.distribution_set = DistributionSet.objects.create(
            aggregated_distribution=self.aggregated_distribution,
            aggregated_distribution__component=self.component
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
