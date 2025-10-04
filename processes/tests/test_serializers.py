"""Serializer tests for the processes module."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from materials.models import Material
from utils.properties.models import Unit

from ..models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)
from ..serializers import (
    ProcessCategorySerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessMaterialSerializer,
    ProcessOperatingParameterSerializer,
)


class ProcessCategorySerializerTestCase(TestCase):
    """Test ProcessCategory serializer."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical",
            description="Test description",
            owner=self.owner,
            publication_status="published",
        )

    def test_serialize_category(self):
        """Serializer should serialize category correctly."""
        serializer = ProcessCategorySerializer(self.category)
        data = serializer.data
        
        self.assertEqual(data["name"], "Thermochemical")
        self.assertEqual(data["description"], "Test description")
        self.assertEqual(data["publication_status"], "published")

    def test_deserialize_category(self):
        """Serializer should deserialize valid data."""
        data = {"name": "New Category", "description": "New description"}
        serializer = ProcessCategorySerializer(data=data)
        
        # Note: owner field is read-only and set in the view
        self.assertTrue(serializer.is_valid())


class ProcessMaterialSerializerTestCase(TestCase):
    """Test ProcessMaterial serializer."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.process = Process.objects.create(name="Test Process", owner=self.owner)
        self.material = Material.objects.create(name="Test Material", owner=self.owner)
        self.unit = Unit.objects.create(name="kg", owner=self.owner)
        
        self.process_material = ProcessMaterial.objects.create(
            process=self.process,
            material=self.material,
            role=ProcessMaterial.Role.INPUT,
            quantity_value=Decimal("10.5"),
            quantity_unit=self.unit,
        )

    def test_serialize_process_material(self):
        """Serializer should serialize process material correctly."""
        serializer = ProcessMaterialSerializer(self.process_material)
        data = serializer.data
        
        self.assertEqual(data["role"], ProcessMaterial.Role.INPUT)
        self.assertEqual(data["role_display"], "Input")
        self.assertEqual(float(data["quantity_value"]), 10.5)


class ProcessOperatingParameterSerializerTestCase(TestCase):
    """Test ProcessOperatingParameter serializer."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.process = Process.objects.create(name="Test Process", owner=self.owner)
        self.unit = Unit.objects.create(name="°C", owner=self.owner)
        
        self.parameter = ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            value_min=Decimal("100"),
            value_max=Decimal("200"),
            unit=self.unit,
        )

    def test_serialize_parameter(self):
        """Serializer should serialize parameter correctly."""
        serializer = ProcessOperatingParameterSerializer(self.parameter)
        data = serializer.data
        
        self.assertEqual(data["parameter"], ProcessOperatingParameter.Parameter.TEMPERATURE)
        self.assertEqual(data["parameter_display"], "Temperature")
        self.assertEqual(float(data["value_min"]), 100)
        self.assertEqual(float(data["value_max"]), 200)


class ProcessListSerializerTestCase(TestCase):
    """Test ProcessListSerializer."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner
        )
        
        self.process = Process.objects.create(
            name="Pyrolysis",
            short_description="Test description",
            mechanism="Thermal Decomposition",
            owner=self.owner,
            publication_status="published",
        )
        self.process.categories.add(self.category)

    def test_serialize_process_list(self):
        """List serializer should include basic process info."""
        serializer = ProcessListSerializer(self.process)
        data = serializer.data
        
        self.assertEqual(data["name"], "Pyrolysis")
        self.assertEqual(data["short_description"], "Test description")
        self.assertEqual(data["mechanism"], "Thermal Decomposition")
        self.assertEqual(data["owner_name"], "test_user")
        self.assertEqual(len(data["categories"]), 1)


class ProcessDetailSerializerTestCase(TestCase):
    """Test ProcessDetailSerializer."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner
        )
        
        self.process = Process.objects.create(
            name="Pyrolysis",
            short_description="Test description",
            mechanism="Thermal Decomposition",
            description="Detailed description",
            owner=self.owner,
            publication_status="published",
        )
        self.process.categories.add(self.category)
        
        # Add materials
        self.material_in = Material.objects.create(name="Wood Chips", owner=self.owner)
        self.material_out = Material.objects.create(name="Bio-oil", owner=self.owner)
        
        ProcessMaterial.objects.create(
            process=self.process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
        )
        ProcessMaterial.objects.create(
            process=self.process,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
        )

    def test_serialize_process_detail(self):
        """Detail serializer should include all process information."""
        serializer = ProcessDetailSerializer(self.process)
        data = serializer.data
        
        self.assertEqual(data["name"], "Pyrolysis")
        self.assertEqual(data["description"], "Detailed description")
        self.assertEqual(len(data["input_materials"]), 1)
        self.assertEqual(len(data["output_materials"]), 1)
        self.assertEqual(data["input_materials"][0]["name"], "Wood Chips")
        self.assertEqual(data["output_materials"][0]["name"], "Bio-oil")
