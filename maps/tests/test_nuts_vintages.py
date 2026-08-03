"""NUTS classification vintages: identity, uniqueness and default resolution."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from ..models import NutsRegion, NutsVintage


class NutsVintageTestCase(TestCase):
    def test_initial_data_seeds_nuts_2021_as_current(self):
        vintage = NutsVintage.objects.get(is_current=True)
        self.assertEqual(vintage.year, 2021)

    def test_str_is_the_year(self):
        self.assertEqual(str(NutsVintage.objects.get(year=2021)), "NUTS 2021")

    def test_current_returns_the_current_vintage(self):
        self.assertEqual(NutsVintage.current().year, 2021)

    def test_resolve_accepts_year_and_prefixed_labels(self):
        self.assertEqual(NutsVintage.resolve("2021").year, 2021)
        self.assertEqual(NutsVintage.resolve("NUTS2021").year, 2021)
        self.assertEqual(NutsVintage.resolve("NUTS 2021").year, 2021)
        self.assertEqual(NutsVintage.resolve(2021).year, 2021)

    def test_resolve_returns_none_for_unknown_or_empty_labels(self):
        self.assertIsNone(NutsVintage.resolve(""))
        self.assertIsNone(NutsVintage.resolve(None))
        self.assertIsNone(NutsVintage.resolve("2024"))
        self.assertIsNone(NutsVintage.resolve("not-a-version"))


class NutsRegionVersionTestCase(TestCase):
    def test_version_defaults_to_the_current_vintage(self):
        region = NutsRegion.objects.create(
            name="Grafschaft Bentheim", country="DE", nuts_id="DE94A", levl_code=3
        )
        self.assertEqual(region.version.year, 2021)

    def test_same_code_can_exist_in_two_vintages(self):
        vintage_2024 = NutsVintage.objects.create(year=2024)
        NutsRegion.objects.create(name="A", country="DE", nuts_id="DEG0B", levl_code=3)
        other = NutsRegion.objects.create(
            name="A", country="DE", nuts_id="DEG0B", levl_code=3, version=vintage_2024
        )
        self.assertEqual(other.version, vintage_2024)
        self.assertEqual(NutsRegion.objects.filter(nuts_id="DEG0B").count(), 2)

    def test_version_is_required_on_paths_that_bypass_save(self):
        """loaddata and QuerySet.update() skip save(); the database must reject NULL.

        A NULL version would also defeat unique_nuts_id_per_version, since
        Postgres treats NULLs in a unique constraint as distinct.
        """
        region = NutsRegion.objects.create(
            name="A", country="DE", nuts_id="DE94A", levl_code=3
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NutsRegion.objects.filter(pk=region.pk).update(version=None)

    def test_code_is_unique_within_a_vintage(self):
        NutsRegion.objects.create(name="A", country="DE", nuts_id="DEG0B", levl_code=3)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NutsRegion.objects.create(
                    name="A duplicate", country="DE", nuts_id="DEG0B", levl_code=3
                )
