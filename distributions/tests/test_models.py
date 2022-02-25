from django.test import TestCase

from ..models import TemporalDistribution, Timestep


class InitialDataTestCase(TestCase):

    def test_base_distribution_is_created_from_migrations(self):
        TemporalDistribution.objects.get(name='Average')
        self.assertEqual(TemporalDistribution.objects.all().count(), 1)

    def test_base_timestep_is_created_from_migrations(self):
        Timestep.objects.get(name='Average')
        self.assertEqual(Timestep.objects.all().count(), 1)

    def test_base_timestep_is_added_to_base_temporal_distribution_during_migrations(self):
        distribution = TemporalDistribution.objects.get(name='Average')
        timestep = Timestep.objects.get(name='Average')
        self.assertEqual(timestep.distribution, distribution)


class TemporalDistributionTestCase(TestCase):

    def test_get_default_temporal_distribution(self):
        default = TemporalDistribution.objects.default()
        self.assertIsInstance(default, TemporalDistribution)
        self.assertEqual(default.name, 'Average')


class TimeStepTestCase(TestCase):

    def test_get_default_timestep(self):
        default = Timestep.objects.default()
        self.assertIsInstance(default, Timestep)
        self.assertEqual(default.name, 'Average')
