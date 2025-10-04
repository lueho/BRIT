"""Comprehensive test suite for the processes module.

This module tests all models, validations, properties, and methods in the processes app.
Organized to follow the project's testing patterns and provide thorough coverage.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from bibliography.models import Source
from materials.models import Material
from utils.properties.models import Unit

from .models import (
    Process,
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessReference,
    validate_internal_or_external_url,
)


# ==============================================================================
# URL Validation Tests
# ==============================================================================


class URLValidationTestCase(TestCase):
    """Test the validate_internal_or_external_url function."""

    def test_accepts_http_urls(self):
        """HTTP URLs should be valid."""
        validate_internal_or_external_url("http://example.com")
        validate_internal_or_external_url("http://example.com/path")

    def test_accepts_https_urls(self):
        """HTTPS URLs should be valid."""
        validate_internal_or_external_url("https://example.com")
        validate_internal_or_external_url("https://example.com/path/to/resource")

    def test_accepts_root_relative_paths(self):
        """Root-relative paths starting with / should be valid."""
        validate_internal_or_external_url("/processes/detail/1/")
        validate_internal_or_external_url("/some/path")

    def test_rejects_relative_paths_without_slash(self):
        """Relative paths not starting with / should be invalid."""
        with self.assertRaises(ValidationError):
            validate_internal_or_external_url("relative/path")

    def test_rejects_javascript_urls(self):
        """JavaScript URLs should be rejected for security."""
        with self.assertRaises(ValidationError):
            validate_internal_or_external_url("javascript:alert('xss')")

    def test_rejects_urls_with_spaces(self):
        """URLs with spaces should be invalid."""
        with self.assertRaises(ValidationError):
            validate_internal_or_external_url("/path with spaces")

    def test_accepts_empty_value(self):
        """Empty values should be accepted (for optional fields)."""
        validate_internal_or_external_url("")
        validate_internal_or_external_url(None)


# ==============================================================================
# Process Category Tests
# ==============================================================================


class ProcessCategoryModelTestCase(TestCase):
    """Test the ProcessCategory model."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="category_owner")

    def test_create_category(self):
        """ProcessCategory can be created with name and owner."""
        category = ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner
        )
        self.assertEqual(category.name, "Thermochemical")
        self.assertEqual(category.owner, self.owner)

    def test_str_representation(self):
        """String representation should return the category name."""
        category = ProcessCategory.objects.create(name="Biochemical", owner=self.owner)
        self.assertEqual(str(category), "Biochemical")

    def test_publication_status_inherited(self):
        """ProcessCategory inherits publication status from NamedUserCreatedObject."""
        category = ProcessCategory.objects.create(
            name="Physical", owner=self.owner, publication_status="published"
        )
        self.assertEqual(category.publication_status, "published")


# ==============================================================================
# Process Model Tests
# ==============================================================================


class ProcessModelTestCase(TestCase):
    """Test the Process model and its relationships."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="process_owner")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner
        )
        self.material_in = Material.objects.create(name="Wood Chips", owner=self.owner)
        self.material_out = Material.objects.create(name="Syngas", owner=self.owner)
        self.unit_celsius = Unit.objects.create(name="°C", owner=self.owner)
        self.unit_percent = Unit.objects.create(name="%", owner=self.owner)
        self.unit_tonne = Unit.objects.create(name="t", owner=self.owner)

    def test_operating_parameter_range_validation(self):
        process = Process.objects.create(name="Invalid Temperature", owner=self.owner)
        parameter = ProcessOperatingParameter(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            value_min=Decimal("200"),
            value_max=Decimal("150"),
            unit=self.unit_celsius,
        )
        with self.assertRaises(ValidationError):
            parameter.full_clean()

    def test_operating_parameter_requires_value(self):
        process = Process.objects.create(name="No Value", owner=self.owner)
        parameter = ProcessOperatingParameter(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.PRESSURE,
        )
        with self.assertRaises(ValidationError):
            parameter.full_clean()

    def test_custom_parameter_requires_name(self):
        process = Process.objects.create(name="Custom", owner=self.owner)
        parameter = ProcessOperatingParameter(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.CUSTOM,
            nominal_value=Decimal("5"),
        )
        with self.assertRaises(ValidationError):
            parameter.full_clean()

        parameter.name = "Residence time"
        parameter.full_clean()  # should not raise when named

    def test_yield_parameter_enforces_percentage_bounds(self):
        process = Process.objects.create(name="Yield", owner=self.owner)
        parameter = ProcessOperatingParameter(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.YIELD,
            nominal_value=Decimal("150"),
            unit=self.unit_percent,
        )
        with self.assertRaises(ValidationError):
            parameter.full_clean()

        parameter.nominal_value = Decimal("85")
        parameter.full_clean()

    def test_process_material_quantity_validation(self):
        process = Process.objects.create(name="Gasification", owner=self.owner)
        material_link = ProcessMaterial(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            quantity_value=Decimal("2.5"),
        )
        with self.assertRaises(ValidationError):
            material_link.full_clean()

        material_link.quantity_unit = self.unit_tonne
        material_link.full_clean()

        material_link_without_value = ProcessMaterial(
            process=process,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
            quantity_unit=self.unit_tonne,
        )
        with self.assertRaises(ValidationError):
            material_link_without_value.full_clean()

    def test_process_material_allows_parallel_streams(self):
        process = Process.objects.create(name="Steam Explosion", owner=self.owner)
        ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            stream_label="Primary",
        )
        ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            stream_label="Recycle",
        )

        self.assertEqual(
            ProcessMaterial.objects.filter(
                process=process,
                material=self.material_in,
                role=ProcessMaterial.Role.INPUT,
            ).count(),
            2,
        )

    def test_input_output_material_relationships(self):
        process = Process.objects.create(
            name="Gasification",
            owner=self.owner,
            short_description="Thermochemical conversion",
        )
        process.categories.add(self.category)

        ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
        )
        ProcessMaterial.objects.create(
            process=process,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
        )

        input_names = [material.name for material in process.input_materials]
        output_names = [material.name for material in process.output_materials]

        self.assertEqual(input_names, [self.material_in.name])
        self.assertEqual(output_names, [self.material_out.name])

    def test_process_sources_property_aggregates_references(self):
        process = Process.objects.create(name="Composting", owner=self.owner)
        source = Source.objects.create(
            title="Reference Title",
            abbreviation="Ref01",
            owner=self.owner,
        )
        ProcessReference.objects.create(process=process, source=source)
        ProcessReference.objects.create(
            process=process,
            title="Custom reference",
            url="https://example.com/reference",
        )

        self.assertEqual(
            list(process.sources.order_by("id").values_list("pk", flat=True)),
            [source.pk],
        )

    def test_process_link_url_validation(self):
        process = Process.objects.create(name="Anaerobic Digestion", owner=self.owner)
        link = ProcessLink(
            process=process,
            label="Run simulation",
            url="javascript:alert('xss')",
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

        link.url = "/processes/types/1/run/"
        link.full_clean()

        link.url = "https://example.com/process"
        link.full_clean()

    def test_process_info_resource_type_validation(self):
        process = Process.objects.create(name="Pyrolysis", owner=self.owner)

        resource = ProcessInfoResource(
            process=process,
            title="Info chart",
            resource_type=ProcessInfoResource.ResourceType.DOCUMENT,
        )
        with self.assertRaises(ValidationError):
            resource.full_clean()

        resource.document = SimpleUploadedFile("chart.pdf", b"filecontent")
        resource.full_clean()

        external_resource = ProcessInfoResource(
            process=process,
            title="External info",
            resource_type=ProcessInfoResource.ResourceType.EXTERNAL,
            url="/relative/path/",
        )
        with self.assertRaises(ValidationError):
            external_resource.full_clean()

        external_resource.url = "https://example.com/info.pdf"
        external_resource.full_clean()

        internal_resource = ProcessInfoResource(
            process=process,
            title="Internal info",
            resource_type=ProcessInfoResource.ResourceType.INTERNAL,
            url="https://example.com/internal",
        )
        with self.assertRaises(ValidationError):
            internal_resource.full_clean()

        internal_resource.url = "/internal/path/"
        internal_resource.full_clean()

    def test_process_reference_requires_source_or_title(self):
        process = Process.objects.create(name="Fermentation", owner=self.owner)
        reference = ProcessReference(process=process)
        with self.assertRaises(ValidationError):
            reference.full_clean()

        custom_reference = ProcessReference(
            process=process,
            title="Example reference",
        )
        custom_reference.full_clean()

        source = Source.objects.create(
            title="Reference Title",
            abbreviation="Ref02",
            owner=self.owner,
        )
        source_reference = ProcessReference(process=process, source=source)
        source_reference.full_clean()

    def test_process_hierarchy(self):
        """Test that processes can have parent-child relationships."""
        parent = Process.objects.create(name="Anaerobic Digestion", owner=self.owner)
        variant1 = Process.objects.create(
            name="Mesophilic AD", parent=parent, owner=self.owner
        )
        variant2 = Process.objects.create(
            name="Thermophilic AD", parent=parent, owner=self.owner
        )

        self.assertEqual(variant1.parent, parent)
        self.assertEqual(list(parent.variants.all()), [variant1, variant2])

    def test_process_short_description(self):
        """Test that short_description field works correctly."""
        process = Process.objects.create(
            name="Pyrolysis",
            short_description="Thermal decomposition without oxygen",
            owner=self.owner,
        )
        self.assertEqual(
            process.short_description, "Thermal decomposition without oxygen"
        )

    def test_process_mechanism(self):
        """Test that mechanism field stores process mechanism."""
        process = Process.objects.create(
            name="Composting", mechanism="Aerobic Decomposition", owner=self.owner
        )
        self.assertEqual(process.mechanism, "Aerobic Decomposition")

    def test_process_image_field(self):
        """Test that image can be attached to process."""
        process = Process.objects.create(name="Gasification", owner=self.owner)
        self.assertFalse(process.image)  # Empty ImageField is falsy

    def test_process_ordering(self):
        """Test that processes are ordered by name then id."""
        Process.objects.create(name="Zeta Process", owner=self.owner)
        Process.objects.create(name="Alpha Process", owner=self.owner)
        Process.objects.create(name="Beta Process", owner=self.owner)

        processes = list(Process.objects.all())
        self.assertEqual(processes[0].name, "Alpha Process")
        self.assertEqual(processes[1].name, "Beta Process")
        self.assertEqual(processes[2].name, "Zeta Process")

    def test_operating_parameters_for_method(self):
        """Test operating_parameters_for convenience method."""
        process = Process.objects.create(name="Test Process", owner=self.owner)
        temp_param1 = ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            nominal_value=Decimal("150"),
            unit=self.unit_celsius,
            order=1,
        )
        temp_param2 = ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            nominal_value=Decimal("200"),
            unit=self.unit_celsius,
            order=2,
        )
        ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.PRESSURE,
            nominal_value=Decimal("5"),
            order=3,
        )

        temp_params = process.operating_parameters_for(
            ProcessOperatingParameter.Parameter.TEMPERATURE
        )
        self.assertEqual(list(temp_params), [temp_param1, temp_param2])

    def test_process_material_stage_and_stream_label(self):
        """Test that stage and stream_label fields work correctly."""
        process = Process.objects.create(name="Complex Process", owner=self.owner)
        material_link = ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            stage="Preprocessing",
            stream_label="Primary feed",
        )
        self.assertEqual(material_link.stage, "Preprocessing")
        self.assertEqual(material_link.stream_label, "Primary feed")

    def test_process_material_optional_flag(self):
        """Test that materials can be marked as optional."""
        process = Process.objects.create(name="Flexible Process", owner=self.owner)
        optional_material = ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            optional=True,
        )
        mandatory_material = ProcessMaterial.objects.create(
            process=process,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
            optional=False,
        )
        self.assertTrue(optional_material.optional)
        self.assertFalse(mandatory_material.optional)

    def test_process_material_notes(self):
        """Test that notes can be added to material links."""
        process = Process.objects.create(name="Documented Process", owner=self.owner)
        material_link = ProcessMaterial.objects.create(
            process=process,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
            notes="Requires pre-drying to <10% moisture content",
        )
        self.assertIn("pre-drying", material_link.notes)

    def test_operating_parameter_basis_field(self):
        """Test that basis field stores measurement conditions."""
        process = Process.objects.create(name="Precise Process", owner=self.owner)
        parameter = ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.YIELD,
            nominal_value=Decimal("75"),
            unit=self.unit_percent,
            basis="dry basis",
        )
        self.assertEqual(parameter.basis, "dry basis")

    def test_operating_parameter_custom_type_with_name(self):
        """Test that custom parameters display their custom name."""
        process = Process.objects.create(name="Custom Process", owner=self.owner)
        parameter = ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.CUSTOM,
            name="Catalyst Loading",
            nominal_value=Decimal("2.5"),
        )
        self.assertIn("Catalyst Loading", str(parameter))

    def test_process_link_open_in_new_tab(self):
        """Test that links can be configured to open in new tab."""
        process = Process.objects.create(name="Linked Process", owner=self.owner)
        link = ProcessLink.objects.create(
            process=process,
            label="External Resource",
            url="https://example.com",
            open_in_new_tab=True,
        )
        self.assertTrue(link.open_in_new_tab)

    def test_process_link_ordering(self):
        """Test that links are ordered by order field then id."""
        process = Process.objects.create(name="Process with Links", owner=self.owner)
        link2 = ProcessLink.objects.create(
            process=process,
            label="Second Link",
            url="/second/",
            order=2,
        )
        link1 = ProcessLink.objects.create(
            process=process,
            label="First Link",
            url="/first/",
            order=1,
        )
        links = list(process.links.all())
        self.assertEqual(links[0], link1)
        self.assertEqual(links[1], link2)

    def test_process_info_resource_target_url_for_document(self):
        """Test that target_url property returns document URL when type is DOCUMENT."""
        process = Process.objects.create(name="Process", owner=self.owner)
        resource = ProcessInfoResource.objects.create(
            process=process,
            title="Info PDF",
            resource_type=ProcessInfoResource.ResourceType.DOCUMENT,
            document=SimpleUploadedFile("info.pdf", b"content"),
        )
        self.assertIn("info.pdf", resource.target_url)

    def test_process_info_resource_target_url_for_url_types(self):
        """Test that target_url returns url field for INTERNAL and EXTERNAL types."""
        process = Process.objects.create(name="Process", owner=self.owner)
        internal = ProcessInfoResource.objects.create(
            process=process,
            title="Internal",
            resource_type=ProcessInfoResource.ResourceType.INTERNAL,
            url="/internal/path/",
        )
        external = ProcessInfoResource.objects.create(
            process=process,
            title="External",
            resource_type=ProcessInfoResource.ResourceType.EXTERNAL,
            url="https://example.com/resource",
        )
        self.assertEqual(internal.target_url, "/internal/path/")
        self.assertEqual(external.target_url, "https://example.com/resource")

    def test_process_reference_str_with_source(self):
        """Test string representation when reference has a source."""
        process = Process.objects.create(name="Process", owner=self.owner)
        source = Source.objects.create(
            title="Test Source", abbreviation="TS01", owner=self.owner
        )
        reference = ProcessReference.objects.create(process=process, source=source)
        self.assertEqual(str(reference), "TS01")

    def test_process_reference_str_with_custom_title(self):
        """Test string representation when reference has custom title."""
        process = Process.objects.create(name="Process", owner=self.owner)
        reference = ProcessReference.objects.create(
            process=process, title="Custom Reference Title"
        )
        self.assertEqual(str(reference), "Custom Reference Title")

    def test_process_reference_ordering(self):
        """Test that references are ordered by order field then id."""
        process = Process.objects.create(name="Process", owner=self.owner)
        ref2 = ProcessReference.objects.create(
            process=process, title="Second Ref", order=2
        )
        ref1 = ProcessReference.objects.create(
            process=process, title="First Ref", order=1
        )
        refs = list(process.references.all())
        self.assertEqual(refs[0], ref1)
        self.assertEqual(refs[1], ref2)
