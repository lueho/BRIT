import csv
from datetime import datetime
from decimal import Decimal
from io import BytesIO, StringIO
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook

from utils.properties.models import Unit

from ..models import (
    ComponentMeasurement,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
)
from ..renderers import (
    SampleCSVRenderer,
    SampleMeasurementsXLSXRenderer,
    SampleXLSXRenderer,
)


class SamplePrecisionExportRendererTestCase(SimpleTestCase):
    def test_csv_and_xlsx_fixed_headers_export_stored_sampling_precision(self):
        data = [
            {
                "name": f"Precision {precision or 'legacy'}",
                "datetime": "2024-08-26T22:00:00Z",
                "datetime_precision": precision,
            }
            for precision in ("", "year", "date", "time")
        ]
        for renderer_class in (SampleCSVRenderer, SampleXLSXRenderer):
            with self.subTest(renderer=renderer_class):
                renderer = renderer_class()
                self.assertEqual(
                    renderer.labels.get("datetime_precision"), "Sampling date precision"
                )
                buffer = BytesIO()
                renderer.render(buffer, data)
                if renderer_class is SampleCSVRenderer:
                    rows = list(
                        csv.reader(StringIO(buffer.getvalue().decode("utf-8-sig")))
                    )
                else:
                    buffer.seek(0)
                    workbook = load_workbook(buffer)
                    rows = list(workbook.active.iter_rows(values_only=True))
                header = rows[0]
                precision_column = header.index("Sampling date precision")
                datetime_column = header.index("Sampling date/time")
                for row, expected in zip(rows[1:], data, strict=True):
                    self.assertEqual(
                        row[precision_column] or "", expected["datetime_precision"]
                    )
                    self.assertEqual(row[datetime_column], expected["datetime"])


class SampleMeasurementsXLSXRendererTestCase(TestCase):
    @override_settings(TIME_ZONE="Europe/Berlin", USE_TZ=True)
    def test_sampling_metadata_uses_precision_and_default_timezone(self):
        material = Material.objects.create(name="Dated renderer material")
        sample = Sample.objects.create(
            name="Dated renderer sample",
            material=material,
            analysis_date=datetime(2024, 9, 1, 13, 45, tzinfo=ZoneInfo("UTC")),
            analysis_laboratory="Renderer lab",
        )
        cases = (
            ("year", datetime(2024, 1, 1), "2024"),
            ("date", datetime(2024, 8, 27), "2024-08-27"),
            ("time", datetime(2024, 8, 27, 14, 30), "2024-08-27 14:30"),
            ("time", datetime(2024, 8, 27), "2024-08-27 00:00"),
            ("", datetime(2024, 8, 27), "2024-08-27"),
            ("", datetime(2024, 8, 27, 14, 30), "2024-08-27 14:30"),
            ("", None, ""),
        )
        for precision, value, expected in cases:
            with self.subTest(precision=precision, value=value):
                sample.datetime = (
                    value.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(
                        ZoneInfo("UTC")
                    )
                    if value
                    else None
                )
                sample.datetime_precision = precision
                sample.save(update_fields=["datetime", "datetime_precision"])
                sample.refresh_from_db()
                original = sample.datetime
                with timezone.override("America/Los_Angeles"):
                    buffer = SampleMeasurementsXLSXRenderer(
                        sample=sample,
                        measurements=sample.component_measurements.all(),
                    ).render()
                workbook = load_workbook(buffer)
                for sheet_name in ("Measurements", "Sample Properties"):
                    metadata = {
                        row[0]: row[1]
                        for row in workbook[sheet_name].iter_rows(
                            min_row=1, max_row=13, max_col=2, values_only=True
                        )
                    }
                    self.assertEqual(metadata["Sample date"] or "", expected)
                    self.assertEqual(metadata["Analysis date"], "2024-09-01")
                    self.assertEqual(metadata["Analysis laboratorium"], "Renderer lab")
                self.assertEqual(sample.datetime, original)

    def test_render_exports_raw_component_measurements(self):
        material = Material.objects.create(name="Renderer Material")
        sample = Sample.objects.create(name="Renderer Sample", material=material)
        group = MaterialComponentGroup.objects.create(name="Renderer Group")
        raw_component = MaterialComponent.objects.create(name="Raw Export Component")
        unit = Unit.objects.filter(name="%").first() or Unit.objects.create(name="%")

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
