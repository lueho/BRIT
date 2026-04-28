from decimal import Decimal

from django.test import TestCase
from openpyxl import load_workbook

from utils.properties.models import Unit

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    WeightShare,
)
from ..renderers import SampleMeasurementsXLSXRenderer


class SampleMeasurementsXLSXRendererTestCase(TestCase):
    def test_render_exports_raw_component_measurements_not_legacy_weightshares(self):
        material = Material.objects.create(name="Renderer Material")
        sample = Sample.objects.create(name="Renderer Sample", material=material)
        group = MaterialComponentGroup.objects.create(name="Renderer Group")
        raw_component = MaterialComponent.objects.create(name="Raw Export Component")
        legacy_component = MaterialComponent.objects.create(
            name="Legacy Share Component"
        )
        unit = Unit.objects.filter(name="%").first() or Unit.objects.create(name="%")

        sample.compositions.all().delete()
        composition = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
        )
        WeightShare.objects.create(
            composition=composition,
            component=legacy_component,
            average=Decimal("0.9"),
            standard_deviation=Decimal("0.1"),
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=raw_component,
            unit=unit,
            average=Decimal("42"),
            standard_deviation=Decimal("1.5"),
        )

        buffer = SampleMeasurementsXLSXRenderer(
            sample=sample,
            measurements=sample.component_measurements.all(),
        ).render()
        workbook = load_workbook(buffer)
        measurements_sheet = workbook["Measurements"]
        exported_values = [
            cell.value for cell in measurements_sheet[16] if cell.value is not None
        ]

        self.assertIn("Raw Export Component", exported_values)
        self.assertIn(42, exported_values)
        self.assertNotIn("Legacy Share Component", exported_values)
