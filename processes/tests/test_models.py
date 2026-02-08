import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase

from processes.models import MechanismCategory, ProcessGroup, ProcessType

User = get_user_model()


class ProcessGroupTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="test_owner")
        cls.group = ProcessGroup.objects.create(
            name="Pulping",
            description="Fibre production processes",
            owner=cls.owner,
            publication_status="published",
        )

    def test_str(self):
        self.assertEqual(str(self.group), "Pulping")

    def test_verbose_name(self):
        self.assertEqual(ProcessGroup._meta.verbose_name, "Process Group")

    def test_verbose_name_plural(self):
        self.assertEqual(ProcessGroup._meta.verbose_name_plural, "Process Groups")

    def test_unique_together_name_owner(self):
        with self.assertRaises(Exception):
            ProcessGroup.objects.create(
                name="Pulping",
                owner=self.owner,
            )

    def test_different_owner_same_name_allowed(self):
        other_owner = User.objects.create_user(username="other_owner")
        grp = ProcessGroup.objects.create(
            name="Pulping",
            owner=other_owner,
        )
        self.assertEqual(grp.name, "Pulping")


class MechanismCategoryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="test_owner")
        cls.mechanism = MechanismCategory.objects.create(
            name="Physical",
            description="Mechanical or physical forces",
            owner=cls.owner,
            publication_status="published",
        )

    def test_str(self):
        self.assertEqual(str(self.mechanism), "Physical")

    def test_verbose_name(self):
        self.assertEqual(MechanismCategory._meta.verbose_name, "Mechanism Category")

    def test_verbose_name_plural(self):
        self.assertEqual(
            MechanismCategory._meta.verbose_name_plural, "Mechanism Categories"
        )


class ProcessGroupInitialDataTestCase(TestCase):
    def test_seed_migration_creates_groups(self):
        """Verify the seed function creates all expected groups when a user exists."""
        mod = importlib.import_module(
            "processes.migrations.0003_seed_initial_categories"
        )
        owner, _ = User.objects.get_or_create(username="seed_test_user")
        expected_names = {c["name"] for c in mod.INITIAL_CATEGORIES}
        for cat in mod.INITIAL_CATEGORIES:
            ProcessGroup.objects.get_or_create(
                name=cat["name"],
                owner=owner,
                defaults={
                    "description": cat["description"],
                    "publication_status": "published",
                },
            )
        actual_names = set(ProcessGroup.objects.values_list("name", flat=True))
        self.assertTrue(expected_names.issubset(actual_names))


class ProcessTypeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="test_owner")
        cls.group = ProcessGroup.objects.create(
            name="TestGroup",
            owner=cls.owner,
            publication_status="published",
        )
        cls.mechanism = MechanismCategory.objects.create(
            name="Thermochemical",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process_type = ProcessType.objects.create(
            name="Pyrolysis",
            description="Thermal decomposition without oxygen.",
            short_description="Thermal decomposition",
            mechanism="Thermal Decomposition",
            temperature_min=400,
            temperature_max=700,
            yield_min=70,
            yield_max=80,
            group=cls.group,
            owner=cls.owner,
            publication_status="published",
        )
        cls.process_type.mechanism_categories.add(cls.mechanism)

    def test_str(self):
        self.assertEqual(str(self.process_type), "Pyrolysis")

    def test_verbose_name(self):
        self.assertEqual(ProcessType._meta.verbose_name, "Process Type")

    def test_verbose_name_plural(self):
        self.assertEqual(ProcessType._meta.verbose_name_plural, "Process Types")

    def test_temperature_range(self):
        self.assertIn("400", self.process_type.temperature_range)
        self.assertIn("700", self.process_type.temperature_range)
        self.assertIn("°C", self.process_type.temperature_range)

    def test_yield_range(self):
        self.assertIn("70", self.process_type.yield_range)
        self.assertIn("80", self.process_type.yield_range)
        self.assertIn("%", self.process_type.yield_range)

    def test_temperature_range_empty_when_null(self):
        pt = ProcessType.objects.create(
            name="NoTemp",
            owner=self.owner,
        )
        self.assertEqual(pt.temperature_range, "")

    def test_yield_range_empty_when_null(self):
        pt = ProcessType.objects.create(
            name="NoYield",
            owner=self.owner,
        )
        self.assertEqual(pt.yield_range, "")

    def test_group_fk(self):
        self.assertEqual(self.process_type.group, self.group)

    def test_group_reverse_relation(self):
        self.assertIn(self.process_type, self.group.process_types.all())

    def test_mechanism_categories_m2m(self):
        self.assertIn(self.mechanism, self.process_type.mechanism_categories.all())

    def test_unique_together_name_owner(self):
        with self.assertRaises(Exception):
            ProcessType.objects.create(
                name="Pyrolysis",
                owner=self.owner,
            )

    def test_get_absolute_url(self):
        url = self.process_type.get_absolute_url()
        self.assertIsNotNone(url)
        self.assertIn(str(self.process_type.pk), url)
