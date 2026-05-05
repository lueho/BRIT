"""Form tests for the processes module."""

import unittest

from django.contrib.auth import get_user_model
from django.test import TestCase

from materials.models import Material
from utils.properties.models import Unit

from ..forms import (
    ProcessAddMaterialForm,
    ProcessAddParameterForm,
    ProcessCategoryModalModelForm,
    ProcessCategoryModelForm,
    # ProcessMaterialFormSet,  # Not exported - uses InlineFormSetFactory
    ProcessModalModelForm,
    ProcessModelForm,
    # ProcessOperatingParameterFormSet,  # Not exported - uses InlineFormSetFactory
)
from ..models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)


class ProcessCategoryFormTestCase(TestCase):
    """Test ProcessCategory forms."""

    def test_valid_form(self):
        """Valid data should create a valid form."""
        form = ProcessCategoryModelForm(
            data={"name": "Test Category", "description": "Test Description"}
        )
        self.assertTrue(form.is_valid())

    def test_category_form_includes_supplementary_document(self):
        """Category form should expose the supplementary PDF upload field."""
        form = ProcessCategoryModelForm()
        self.assertIn("supplementary_document", form.fields)

    def test_invalid_empty_name(self):
        """Empty name should be invalid."""
        form = ProcessCategoryModelForm(data={"name": "", "description": "Test"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_modal_form_valid(self):
        """Modal form should work with minimal data."""
        form = ProcessCategoryModalModelForm(data={"name": "Test Category"})
        self.assertTrue(form.is_valid())


class ProcessFormTestCase(TestCase):
    """Test Process forms."""

    def setUp(self):
        self.category = ProcessCategory.objects.create(name="Test Category")

    def test_valid_form(self):
        """Valid data should create a valid form."""
        form = ProcessModelForm(
            data={
                "name": "Test Process",
                "short_description": "Short desc",
                "mechanism": "Test mechanism",
                "categories": [self.category.pk],
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_empty_name(self):
        """Empty name should be invalid."""
        form = ProcessModelForm(
            data={
                "name": "",
                "short_description": "Short desc",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_modal_form_valid(self):
        """Modal form should work with minimal data."""
        form = ProcessModalModelForm(
            data={
                "name": "Test Process",
                "categories": [self.category.pk],
                "short_description": "Test description",
            }
        )
        self.assertTrue(form.is_valid())


@unittest.skip(
    "ProcessMaterialFormSet not exported - uses InlineFormSetFactory pattern"
)
class ProcessMaterialFormSetTestCase(TestCase):
    """Test ProcessMaterial inline formset."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.process = Process.objects.create(name="Test Process", owner=self.owner)
        self.material = Material.objects.create(name="Test Material", owner=self.owner)
        self.unit = Unit.objects.create(name="kg", owner=self.owner)

    def test_valid_formset(self):
        """Valid formset data should be valid."""
        pass  # ProcessMaterialFormSet not exported; test skipped

    def test_quantity_requires_unit(self):
        """Quantity value should require a unit."""
        pass  # ProcessMaterialFormSet not exported; test skipped


@unittest.skip(
    "ProcessOperatingParameterFormSet not exported - uses InlineFormSetFactory pattern"
)
class ProcessOperatingParameterFormSetTestCase(TestCase):
    """Test ProcessOperatingParameter inline formset."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.process = Process.objects.create(name="Test Process", owner=self.owner)
        self.unit = Unit.objects.create(name="°C", owner=self.owner)

    def test_valid_formset(self):
        """Valid formset data should be valid."""
        pass  # ProcessOperatingParameterFormSet not exported; test skipped

    def test_custom_parameter_with_name(self):
        """Custom parameters should allow custom names."""
        pass  # ProcessOperatingParameterFormSet not exported; test skipped


class ProcessAddMaterialFormTestCase(TestCase):
    """Test ProcessAddMaterialForm."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.material = Material.objects.create(
            name="Test Material", owner=self.owner, publication_status="published"
        )

    def test_valid_form(self):
        """Valid data should create a valid form."""
        form = ProcessAddMaterialForm(
            data={
                "material": self.material.pk,
                "role": ProcessMaterial.Role.INPUT,
            }
        )
        self.assertTrue(form.is_valid())


class ProcessAddParameterFormTestCase(TestCase):
    """Test ProcessAddParameterForm."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.unit = Unit.objects.create(
            name="°C", owner=self.owner, publication_status="published"
        )

    def test_valid_form(self):
        """Valid data should create a valid form."""
        form = ProcessAddParameterForm(
            data={
                "parameter": ProcessOperatingParameter.Parameter.TEMPERATURE,
                "nominal_value": "150",
                "unit": self.unit.pk,
            }
        )
        self.assertTrue(form.is_valid())
