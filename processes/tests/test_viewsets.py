"""ViewSet tests for the processes module API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from materials.models import Material
from utils.properties.models import Unit

from ..models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)


class ProcessCategoryViewSetTestCase(APITestCase):
    """Test ProcessCategory API endpoints."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category1 = ProcessCategory.objects.create(
            name="Thermochemical",
            description="Test description",
            owner=self.owner,
            publication_status="published",
        )
        self.category2 = ProcessCategory.objects.create(
            name="Biochemical",
            owner=self.owner,
            publication_status="published",
        )

    def test_list_categories(self):
        """API should list published categories."""
        response = self.client.get("/processes/api/categories/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_category(self):
        """API should retrieve a single category."""
        response = self.client.get(f"/processes/api/categories/{self.category1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Thermochemical")

    def test_search_categories(self):
        """API should support searching categories."""
        response = self.client.get("/processes/api/categories/?search=Thermo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_category_processes_action(self):
        """API should return processes in a category."""
        process = Process.objects.create(
            name="Test Process",
            owner=self.owner,
            publication_status="published",
        )
        process.categories.add(self.category1)
        
        response = self.client.get(
            f"/processes/api/categories/{self.category1.pk}/processes/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ProcessViewSetTestCase(APITestCase):
    """Test Process API endpoints."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical",
            owner=self.owner,
            publication_status="published",
        )
        
        self.process1 = Process.objects.create(
            name="Pyrolysis",
            short_description="Thermal decomposition",
            mechanism="Thermal Decomposition",
            owner=self.owner,
            publication_status="published",
        )
        self.process1.categories.add(self.category)
        
        self.process2 = Process.objects.create(
            name="Gasification",
            mechanism="Partial Oxidation",
            owner=self.owner,
            publication_status="published",
        )
        
        # Add materials
        self.material_in = Material.objects.create(
            name="Wood Chips",
            owner=self.owner,
            publication_status="published",
        )
        self.material_out = Material.objects.create(
            name="Bio-oil",
            owner=self.owner,
            publication_status="published",
        )
        
        ProcessMaterial.objects.create(
            process=self.process1,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
        )
        ProcessMaterial.objects.create(
            process=self.process1,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
        )
        
        # Add operating parameters
        self.unit = Unit.objects.create(
            name="°C",
            owner=self.owner,
            publication_status="published",
        )
        
        ProcessOperatingParameter.objects.create(
            process=self.process1,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            value_min=Decimal("400"),
            value_max=Decimal("700"),
            unit=self.unit,
        )

    def test_list_processes(self):
        """API should list published processes."""
        response = self.client.get("/processes/api/processes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_process(self):
        """API should retrieve a single process with full details."""
        response = self.client.get(f"/processes/api/processes/{self.process1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Pyrolysis")
        self.assertIn("input_materials", response.data)
        self.assertIn("output_materials", response.data)

    def test_search_processes(self):
        """API should support searching processes."""
        response = self.client.get("/processes/api/processes/?search=Pyro")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_materials_action(self):
        """API should return process materials."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/materials/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("inputs", response.data)
        self.assertIn("outputs", response.data)
        self.assertEqual(len(response.data["inputs"]), 1)
        self.assertEqual(len(response.data["outputs"]), 1)

    def test_parameters_action(self):
        """API should return operating parameters."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/parameters/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_parameters_by_type_action(self):
        """API should return parameters grouped by type."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/parameters_by_type/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Temperature", response.data)

    def test_by_category_action(self):
        """API should group processes by category."""
        response = self.client.get("/processes/api/processes/by_category/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))

    def test_by_mechanism_action(self):
        """API should group processes by mechanism."""
        response = self.client.get("/processes/api/processes/by_mechanism/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Thermal Decomposition", response.data)
        self.assertIn("Partial Oxidation", response.data)

    def test_variants_action(self):
        """API should return process variants."""
        variant = Process.objects.create(
            name="Fast Pyrolysis",
            parent=self.process1,
            owner=self.owner,
            publication_status="published",
        )
        
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/variants/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Fast Pyrolysis")
