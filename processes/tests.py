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
)


class ProcessModelTestCase(TestCase):
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
