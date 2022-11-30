from django.db.utils import IntegrityError
from django.test import TestCase
from users.models import get_default_owner

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

    def test_name_and_owner_unique_together(self):
        default_timestep = Timestep.objects.default()
        with self.assertRaises(IntegrityError):
            TemporalDistribution.objects.create(owner=default_timestep.owner, name=default_timestep.name)


class TimeStepTestCase(TestCase):

    def test_get_default_timestep(self):
        default = Timestep.objects.default()
        self.assertIsInstance(default, Timestep)
        self.assertEqual(default.name, 'Average')

    def test_name_and_owner_unique_together(self):
        default_timestep = Timestep.objects.default()
        default_distribution = TemporalDistribution.objects.default()
        with self.assertRaises(IntegrityError):
            Timestep.objects.create(
                owner=default_timestep.owner,
                name=default_timestep.name,
                distribution=default_distribution
            )

    def test_abbreviated(self):
        self.assertEqual('Jan', Timestep.objects.get(name='January').abbreviated)
