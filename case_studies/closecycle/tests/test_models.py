"""Tests for Showcase connections to materials, samples, processes and scenarios."""

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

    def test_showcase_process_unique_per_showcase(self):
        ShowcaseProcess.objects.create(
            showcase=self.showcase, process=self.process_a, order=1
        )
        with self.assertRaises(IntegrityError):
            ShowcaseProcess.objects.create(
                showcase=self.showcase, process=self.process_a, order=2
            )

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
