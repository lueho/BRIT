from datetime import date

from django.test import SimpleTestCase

from sources.waste_collection.management.commands import (
    import_bw_2024_collections,
    import_bw_2024_standalone,
)


class BW2024ImportMappingTests(SimpleTestCase):
    def _build_row(self):
        row = [None] * (max(import_bw_2024_collections._COL.values()) + 1)
        row[import_bw_2024_collections._COL["catchment_name"]] = "Test Catchment"
        row[import_bw_2024_collections._COL["nuts_or_lau_id"]] = "DE123"
        row[import_bw_2024_collections._COL["collector"]] = "Test Collector"
        row[import_bw_2024_collections._COL["collection_system"]] = "Door to door"
        row[import_bw_2024_collections._COL["waste_category"]] = "Residual waste"
        row[import_bw_2024_collections._COL["allowed_materials"]] = "Food waste"
        row[import_bw_2024_collections._COL["forbidden_materials"]] = "Glass"
        row[import_bw_2024_collections._COL["fee_system"]] = "Flat fee"
        row[import_bw_2024_collections._COL["frequency"]] = "Fixed; 26 per year"
        row[import_bw_2024_collections._COL["connection_type"]] = "Voluntary"
        row[import_bw_2024_collections._COL["conn_rate_basis"]] = "households"
        row[import_bw_2024_collections._COL["description"]] = (
            "Updated import description"
        )
        row[import_bw_2024_collections._COL["sources"]] = (
            "Collection of soft materials (leaves, lawn)."
        )
        row[import_bw_2024_collections._COL["sources_new"]] = (
            "https://example.com/a.pdf, not-a-url, https://example.com/b.pdf"
        )
        row[import_bw_2024_collections._COL["valid_from"]] = date(2024, 1, 1)

        for col, year in zip(range(27, 34), range(2015, 2022), strict=True):
            row[col] = float(year - 2000)
        for col, year in zip(range(34, 38), range(2021, 2025), strict=True):
            row[col] = float(year - 2000)

        return row

    def _assert_total_amount_mapping(self, module):
        property_values = module._collect_property_values(self._build_row())

        self.assertEqual(
            property_values,
            [
                {
                    "property_id": module._PROP_SPECIFIC,
                    "unit_name": module._UNIT_KG,
                    "year": year,
                    "average": float(year - 2000),
                }
                for year in range(2015, 2022)
            ]
            + [
                {
                    "property_id": module._PROP_TOTAL,
                    "unit_name": module._UNIT_MG,
                    "year": year,
                    "average": float(year - 2000),
                }
                for year in range(2021, 2025)
            ],
        )

    def test_management_command_maps_all_amount_columns_to_total_mg(self):
        self._assert_total_amount_mapping(import_bw_2024_collections)

    def test_standalone_script_maps_all_amount_columns_to_total_mg(self):
        self._assert_total_amount_mapping(import_bw_2024_standalone)

    def test_management_command_row_layout_matches_current_workbook(self):
        record = import_bw_2024_collections._row_to_record(self._build_row())

        self.assertEqual(record["description"], "Updated import description")
        self.assertEqual(record["valid_from"], date(2024, 1, 1))
        self.assertIsNone(record["valid_until"])
        self.assertEqual(
            record["sources"],
            ["Collection of soft materials (leaves, lawn).", "not-a-url"],
        )
        self.assertEqual(
            record["flyer_urls"],
            ["https://example.com/a.pdf", "https://example.com/b.pdf"],
        )
        self.assertEqual(len(record["property_values"]), 11)

    def test_standalone_row_layout_matches_current_workbook(self):
        record = import_bw_2024_standalone._row_to_record(self._build_row())

        self.assertEqual(record["description"], "Updated import description")
        self.assertEqual(record["valid_from"], "2024-01-01")
        self.assertIsNone(record["valid_until"])
        self.assertEqual(
            record["sources"],
            ["Collection of soft materials (leaves, lawn).", "not-a-url"],
        )
        self.assertEqual(
            record["flyer_urls"],
            ["https://example.com/a.pdf", "https://example.com/b.pdf"],
        )
        self.assertEqual(len(record["property_values"]), 11)
