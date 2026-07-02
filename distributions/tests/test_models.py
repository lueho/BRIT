from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Period, TemporalDistribution, Timestep


class InitialDataTestCase(TestCase):
    def test_base_distribution_is_created_from_migrations(self):
        TemporalDistribution.objects.get(name="Average")

    def test_base_timestep_is_created_from_migrations(self):
        Timestep.objects.get(name="Average")

    def test_base_timestep_is_added_to_base_temporal_distribution_during_migrations(
        self,
    ):
        distribution = TemporalDistribution.objects.get(name="Average")
        timestep = Timestep.objects.get(name="Average")
        self.assertEqual(timestep.distribution, distribution)

    def test_months_of_the_year_distribution_from_migrations(self):
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        for month in (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ):
            distribution.timestep_set.get(name=month)


class TemporalDistributionTestCase(TestCase):
    def test_get_default_temporal_distribution(self):
        default = TemporalDistribution.objects.default()
        self.assertIsInstance(default, TemporalDistribution)
        self.assertEqual(default.name, "Average")

    def test_name_and_owner_unique_together(self):
        default_timestep = Timestep.objects.default()
        with self.assertRaises(IntegrityError):
            TemporalDistribution.objects.create(
                owner=default_timestep.owner, name=default_timestep.name
            )


class TimeStepTestCase(TestCase):
    def test_get_default_timestep(self):
        default = Timestep.objects.default()
        self.assertIsInstance(default, Timestep)
        self.assertEqual(default.name, "Average")

    def test_name_and_owner_unique_together(self):
        default_timestep = Timestep.objects.default()
        default_distribution = TemporalDistribution.objects.default()
        with self.assertRaises(IntegrityError):
            Timestep.objects.create(
                owner=default_timestep.owner,
                name=default_timestep.name,
                distribution=default_distribution,
            )

    def test_abbreviated(self):
        self.assertEqual("Jan", Timestep.objects.get(name="January").abbreviated)

    def test_add_next_order_value_assigns_incrementing_order(self):
        """The post_save signal must assign monotonically increasing order values."""
        dist = TemporalDistribution.objects.create(name="Order Test Distribution")
        ts1 = Timestep.objects.create(name="Order TS 1", distribution=dist)
        ts2 = Timestep.objects.create(name="Order TS 2", distribution=dist)
        ts3 = Timestep.objects.create(name="Order TS 3", distribution=dist)
        self.assertLess(ts1.order, ts2.order)
        self.assertLess(ts2.order, ts3.order)

    def test_add_next_order_value_is_atomic(self):
        """The post_save order assignment must use transaction.atomic + select_for_update."""
        dist = TemporalDistribution.objects.create(name="Atomic Order Distribution")
        ts1 = Timestep.objects.create(name="Atomic TS 1", distribution=dist)
        ts2 = Timestep.objects.create(name="Atomic TS 2", distribution=dist)
        ts1.refresh_from_db()
        ts2.refresh_from_db()
        self.assertEqual(ts2.order, ts1.order + 10)


class PeriodTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.period = Period.objects.get(
            distribution=TemporalDistribution.objects.get(name="Months of the year"),
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )

    def test_unique_together(self):
        with self.assertRaises(IntegrityError):
            Period.objects.create(
                distribution=self.period.distribution,
                first_timestep=self.period.first_timestep,
                last_timestep=self.period.last_timestep,
            )

    def test_str_contains_start_and_end(self):
        self.assertEqual("Period: Jan. through Dec.", self.period.__str__())
