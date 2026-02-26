from collections import OrderedDict
from io import BytesIO
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from openpyxl import load_workbook

from ..export_registry import (
    EXPORT_REGISTRY,
    ExportSpec,
    get_export_spec,
    register_export,
)
from ..renderers import BaseCSVRenderer, BaseXLSXRenderer


class ExportRegistryTestCase(SimpleTestCase):
    """Tests for the export registry functions."""

    def setUp(self):
        self._original_registry = EXPORT_REGISTRY.copy()

    def tearDown(self):
        EXPORT_REGISTRY.clear()
        EXPORT_REGISTRY.update(self._original_registry)

    def test_register_and_retrieve_spec(self):
        """Registered spec can be retrieved by label."""
        filterset = MagicMock()
        serializer = MagicMock()
        renderers = {"csv": MagicMock()}

        register_export("auth.User", filterset, serializer, renderers)

        spec = get_export_spec("auth.User")
        self.assertIsInstance(spec, ExportSpec)
        self.assertIs(spec.model, User)
        self.assertIs(spec.filterset, filterset)
        self.assertIs(spec.serializer, serializer)
        self.assertEqual(spec.renderers, renderers)

    def test_get_unknown_label_raises_key_error(self):
        """Requesting an unregistered label should raise KeyError."""
        with self.assertRaises(KeyError):
            get_export_spec("nonexistent.Model")

    def test_register_overwrites_existing_entry(self):
        """Re-registering the same label should overwrite the previous entry."""
        register_export("auth.User", MagicMock(), MagicMock(), {})
        new_serializer = MagicMock()
        register_export("auth.User", MagicMock(), new_serializer, {})

        spec = get_export_spec("auth.User")
        self.assertIs(spec.serializer, new_serializer)


class BaseXLSXRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.renderer = BaseXLSXRenderer()
        self.renderer.workbook_options = {"in_memory": True}
        self.content = [OrderedDict({"column_1": "content", "column_2": "content"})]
        self.file = BytesIO()

    def test_creates_empty_xlsx_sheet_if_handed_empty_data_dictionary(self):
        self.renderer.render(self.file, {})
        wb = load_workbook(self.file)
        self.assertEqual(1, len(wb.sheetnames))
        self.assertEqual("sheet 1", wb.sheetnames[0])

    def test_uses_dictionary_keys_for_header_if_labels_are_missing(self):
        self.renderer.render(self.file, self.content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("column_1", ws.cell(row=1, column=1).value)
        self.assertEqual("column_2", ws.cell(row=1, column=2).value)

    def test_maintains_order_of_dict_keys(self):
        self.renderer.labels = {"column_2": "Column 2", "column_1": "Column 1"}
        self.renderer.render(self.file, self.content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("Column 2", ws.cell(row=1, column=1).value)
        self.assertEqual("Column 1", ws.cell(row=1, column=2).value)

    def test_writes_data_values_to_cells(self):
        content = [OrderedDict({"col_a": "value_a", "col_b": 42})]
        self.renderer.render(self.file, content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("value_a", ws.cell(row=2, column=1).value)
        self.assertEqual(42, ws.cell(row=2, column=2).value)

    def test_writes_multiple_rows(self):
        content = [
            OrderedDict({"col": "row1"}),
            OrderedDict({"col": "row2"}),
            OrderedDict({"col": "row3"}),
        ]
        self.renderer.render(self.file, content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("row1", ws.cell(row=2, column=1).value)
        self.assertEqual("row2", ws.cell(row=3, column=1).value)
        self.assertEqual("row3", ws.cell(row=4, column=1).value)

    def test_preset_column_order_controls_output_columns(self):
        self.renderer.column_order = ["column_2", "column_1"]
        self.renderer.render(self.file, self.content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("column_2", ws.cell(row=1, column=1).value)
        self.assertEqual("column_1", ws.cell(row=1, column=2).value)
        self.assertEqual("content", ws.cell(row=2, column=1).value)
        self.assertEqual("content", ws.cell(row=2, column=2).value)

    def test_labels_applied_with_preset_column_order(self):
        self.renderer.column_order = ["column_2", "column_1"]
        self.renderer.labels = {"column_1": "First", "column_2": "Second"}
        self.renderer.render(self.file, self.content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("Second", ws.cell(row=1, column=1).value)
        self.assertEqual("First", ws.cell(row=1, column=2).value)

    def test_missing_key_in_data_row_renders_none(self):
        content = [OrderedDict({"col_a": "present"})]
        self.renderer.column_order = ["col_a", "col_b"]
        self.renderer.render(self.file, content)
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertEqual("present", ws.cell(row=2, column=1).value)
        self.assertIsNone(ws.cell(row=2, column=2).value)

    def test_empty_list_creates_sheet_with_no_data_rows(self):
        self.renderer.render(self.file, [])
        wb = load_workbook(self.file)
        ws = wb.active
        self.assertIsNone(ws.cell(row=1, column=1).value)


class BaseCSVRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.renderer = BaseCSVRenderer()
        self.file = BytesIO()

    def test_writes_csv_content_to_file(self):
        content = [OrderedDict({"col_a": "val1", "col_b": "val2"})]
        self.renderer.render(self.file, content)
        output = self.file.getvalue().decode("utf-8")
        self.assertIn("col_a", output)
        self.assertIn("val1", output)
        self.assertIn("col_b", output)
        self.assertIn("val2", output)

    def test_writes_multiple_rows_to_csv(self):
        content = [
            OrderedDict({"col": "row1"}),
            OrderedDict({"col": "row2"}),
        ]
        self.renderer.render(self.file, content)
        lines = self.file.getvalue().decode("utf-8").strip().splitlines()
        self.assertEqual(3, len(lines))

    def test_empty_data_produces_empty_output(self):
        self.renderer.render(self.file, [])
        output = self.file.getvalue()
        self.assertEqual(b"", output)
