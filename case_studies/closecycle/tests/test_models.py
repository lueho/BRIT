"""Tests for Showcase connections to materials, samples, processes and scenarios."""

from importlib import import_module

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.test import TestCase

from case_studies.closecycle.models import (
    Showcase,
    ShowcaseMaterial,
    ShowcaseProcess,
)
from inventories.models import Scenario
from maps.models import Catchment, Region
from materials.models import Material, MaterialCategory, Sample, SampleSeries
from processes.models import Process


class ShowcaseConnectionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Test Region")
        cls.catchment = Catchment.objects.create(
            name="Test Catchment", region=cls.region
        )
        cls.showcase = Showcase.objects.create(
            name="Test Showcase", region=cls.region, catchment=cls.catchment
        )
        cls.bioresource = Material.objects.create(name="Grass cuttings")
        cls.intermediate = Material.objects.create(name="Silage")
        cls.product = Material.objects.create(name="Compost")
        cls.process_a = Process.objects.create(name="Composting")
        cls.process_b = Process.objects.create(name="Shredding")

    def test_materials_linked_with_roles(self):
        ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.bioresource,
            role=ShowcaseMaterial.Role.INPUT,
        )
        ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.product,
            role=ShowcaseMaterial.Role.PRODUCT,
        )
        self.assertEqual(
            {self.bioresource, self.product}, set(self.showcase.materials.all())
        )
        links = self.showcase.showcase_materials.all()
        self.assertEqual(2, len(links))
        self.assertEqual({"input", "product"}, {link.role for link in links})

    def test_material_roles(self):
        self.assertEqual(
            {"input", "intermediate", "product"},
            {choice[0] for choice in ShowcaseMaterial.Role.choices},
        )

    def test_same_material_allowed_in_different_roles(self):
        ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.intermediate,
            role=ShowcaseMaterial.Role.INPUT,
        )
        ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.intermediate,
            role=ShowcaseMaterial.Role.PRODUCT,
        )
        self.assertEqual(2, self.showcase.showcase_materials.count())

    def test_showcase_material_unique_per_role(self):
        ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.bioresource,
            role=ShowcaseMaterial.Role.INPUT,
        )
        with self.assertRaises(IntegrityError):
            ShowcaseMaterial.objects.create(
                showcase=self.showcase,
                material=self.bioresource,
                role=ShowcaseMaterial.Role.INPUT,
            )

    def test_showcase_material_ordering(self):
        second = ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.product,
            role=ShowcaseMaterial.Role.INPUT,
            order=2,
        )
        first = ShowcaseMaterial.objects.create(
            showcase=self.showcase,
            material=self.bioresource,
            role=ShowcaseMaterial.Role.INPUT,
            order=1,
        )
        self.assertEqual(
            [first, second],
            list(
                self.showcase.showcase_materials.filter(
                    role=ShowcaseMaterial.Role.INPUT
                )
            ),
        )

    def test_processes_form_ordered_chain(self):
        ShowcaseProcess.objects.create(
            showcase=self.showcase, process=self.process_b, order=1
        )
        ShowcaseProcess.objects.create(
            showcase=self.showcase, process=self.process_a, order=2
        )
        self.assertEqual(
            {self.process_a, self.process_b}, set(self.showcase.processes.all())
        )
        self.assertEqual([self.process_b, self.process_a], self.showcase.process_chain)

    def test_process_can_repeat_at_later_chain_position(self):
        for order, process in enumerate(
            [self.process_b, self.process_a, self.process_b], start=1
        ):
            ShowcaseProcess.objects.create(
                showcase=self.showcase, process=process, order=order
            )
        self.assertEqual(
            [self.process_b, self.process_a, self.process_b],
            self.showcase.process_chain,
        )

    def test_process_chain_uses_prefetched_links(self):
        ShowcaseProcess.objects.create(
            showcase=self.showcase, process=self.process_b, order=1
        )
        ShowcaseProcess.objects.create(
            showcase=self.showcase, process=self.process_a, order=2
        )
        showcase = Showcase.objects.prefetch_related("showcase_processes__process").get(
            pk=self.showcase.pk
        )
        with self.assertNumQueries(0):
            self.assertEqual([self.process_b, self.process_a], showcase.process_chain)

    def test_catchment_is_optional(self):
        showcase = Showcase.objects.create(name="No catchment")
        self.assertIsNone(showcase.catchment)

    def test_samples_and_sample_series_m2m(self):
        series = SampleSeries.objects.create(name="Series", material=self.bioresource)
        sample = Sample.objects.create(name="S1", material=self.bioresource)
        self.showcase.samples.add(sample)
        self.showcase.sample_series.add(series)
        self.assertEqual([sample], list(self.showcase.samples.all()))
        self.assertEqual([series], list(self.showcase.sample_series.all()))
        self.assertIn(self.showcase, series.showcases.all())

    def test_scenario_belongs_to_showcase(self):
        scenario = Scenario.objects.create(
            name="Showcase scenario",
            region=self.region,
            catchment=self.catchment,
            showcase=self.showcase,
        )
        self.assertEqual([scenario], list(self.showcase.scenarios.all()))

    def test_scenario_survives_showcase_deletion(self):
        scenario = Scenario.objects.create(
            name="Showcase scenario", showcase=self.showcase
        )
        self.showcase.delete()
        scenario.refresh_from_db()
        self.assertIsNone(scenario.showcase)

    def test_product_material_category_exists(self):
        """The 'Product' material category is created by a data migration."""
        self.assertTrue(
            MaterialCategory.objects.filter(
                name="Product", publication_status="published"
            ).exists()
        )


class ProductMaterialCategoryMigrationTestCase(TestCase):
    def test_migration_tolerates_product_categories_of_other_owners(self):
        migration = import_module("materials.migrations.0030_product_material_category")
        User = get_user_model()
        for username in ("alice", "bob"):
            MaterialCategory.objects.create(
                name="Product", owner=User.objects.create(username=username)
            )

        migration.ensure_product_category(django_apps, None)

        default_owner = User.objects.get(
            username=settings.DEFAULT_OBJECT_OWNER_USERNAME
        )
        self.assertEqual(
            1,
            MaterialCategory.objects.filter(
                name="Product", owner=default_owner
            ).count(),
        )


class ShowcaseVisibleConnectionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create(username="connection_owner")
        cls.other = User.objects.create(username="connection_other")
        region = Region.objects.create(name="Visible Region")
        cls.public_catchment = Catchment.objects.create(
            name="Public Catchment", region=region, publication_status="published"
        )
        cls.private_catchment = Catchment.objects.create(
            name="Private Catchment", region=region, owner=cls.owner
        )
        cls.showcase = Showcase.objects.create(
            name="Visible Showcase",
            region=region,
            catchment=cls.private_catchment,
            publication_status="published",
        )
        public = {"publication_status": "published"}
        private = {"owner": cls.owner}
        cls.public_material = Material.objects.create(name="Public Mat", **public)
        cls.private_material = Material.objects.create(name="Private Mat", **private)
        cls.public_process = Process.objects.create(name="Public Proc", **public)
        cls.private_process = Process.objects.create(name="Private Proc", **private)
        cls.public_sample = Sample.objects.create(
            name="Public Sample", material=cls.public_material, **public
        )
        cls.private_sample = Sample.objects.create(
            name="Private Sample", material=cls.public_material, **private
        )
        cls.public_series = SampleSeries.objects.create(
            name="Public Series", material=cls.public_material, **public
        )
        cls.private_series = SampleSeries.objects.create(
            name="Private Series", material=cls.public_material, **private
        )
        cls.public_scenario = Scenario.objects.create(
            name="Public Scenario", showcase=cls.showcase, **public
        )
        cls.private_scenario = Scenario.objects.create(
            name="Private Scenario", showcase=cls.showcase, **private
        )
        for material in (cls.public_material, cls.private_material):
            cls.showcase.showcase_materials.create(
                material=material, role=ShowcaseMaterial.Role.INPUT
            )
        for order, process in enumerate((cls.public_process, cls.private_process)):
            cls.showcase.showcase_processes.create(process=process, order=order)
        cls.showcase.samples.add(cls.public_sample, cls.private_sample)
        cls.showcase.sample_series.add(cls.public_series, cls.private_series)

    def assert_connections(self, showcase, user, *, include_private):
        def expected(public_obj, private_obj):
            return [public_obj, private_obj] if include_private else [public_obj]

        self.assertEqual(
            expected(self.public_material, self.private_material),
            [link.material for link in showcase.visible_material_links(user)],
        )
        self.assertEqual(
            expected(self.public_process, self.private_process),
            showcase.visible_process_chain(user),
        )
        self.assertEqual(
            set(expected(self.public_sample, self.private_sample)),
            set(showcase.visible_samples(user)),
        )
        self.assertEqual(
            set(expected(self.public_series, self.private_series)),
            set(showcase.visible_sample_series(user)),
        )
        self.assertEqual(
            set(expected(self.public_scenario, self.private_scenario)),
            set(showcase.visible_scenarios(user)),
        )
        self.assertEqual(
            self.private_catchment if include_private else None,
            showcase.visible_catchment(user),
        )

    def test_anonymous_sees_only_published_connections(self):
        self.assert_connections(self.showcase, AnonymousUser(), include_private=False)

    def test_other_user_sees_only_published_connections(self):
        self.assert_connections(self.showcase, self.other, include_private=False)

    def test_owner_of_linked_records_sees_them(self):
        self.assert_connections(self.showcase, self.owner, include_private=True)

    def test_prefetched_connections_are_filtered_without_extra_queries(self):
        for user, include_private in ((AnonymousUser(), False), (self.owner, True)):
            with self.subTest(user=user):
                showcase = Showcase.prefetch_visible_connections(
                    Showcase.objects.filter(pk=self.showcase.pk), user
                ).get()
                with self.assertNumQueries(0):
                    self.assert_connections(
                        showcase, user, include_private=include_private
                    )
