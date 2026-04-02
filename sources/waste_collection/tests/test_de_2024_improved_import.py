from datetime import date

from django.test import SimpleTestCase

from sources.waste_collection.management.commands import (
    import_de_2024_improved_standalone,
)


class German2024ImprovedStandaloneImportTests(SimpleTestCase):
    def _build_row(self, header):
        row = [None] * len(header)
        index = {name: position for position, name in enumerate(header)}
        row[index["Catchment"]] = "Test Catchment"
        row[index["NUTS/LAU Id"]] = "DE123"
        row[index["Collector"]] = "Test Collector"
        row[index["Collection System"]] = "Door to door"
        row[index["Waste Category"]] = "Residual waste"
        row[index["Introduction of collection system (Year)"]] = 1998
        row[index["Connection type"]] = "Voluntary"
        row[index["Allowed Materials"]] = "Food waste"
        row[index["Forbidden Materials"]] = "Glass"
        row[index["Fee System"]] = "Flat fee"
        row[index["Frequency"]] = "Fixed; 26 per year"
        row[index["Minimum bin size (L)"]] = 120
        row[index["Minimum required specific bin capacity (L/reference unit)"]] = 10
        row[index["Reference unit for minimum required specific bin capacity"]] = (
            "person"
        )
        row[index["Comments"]] = "Updated import description"
        row[index["Sources_new"]] = (
            "Personal communication with district office, "
            "https://example.com/archive.pdf"
        )
        row[index["Weblinks"]] = "https://example.com/a.pdf, https://example.com/b.pdf"
        if "Bibliography Sources" in index:
            row[index["Bibliography Sources"]] = "District annual report 2024"
        row[index["Valid from"]] = date(2024, 1, 1)
        if "Valid until" in index:
            row[index["Valid until"]] = None
        if "Specific Waste Collected 2021" in index:
            row[index["Specific Waste Collected 2021"]] = 21.0
        if "Specific Waste Collected 2021 Unit" in index:
            row[index["Specific Waste Collected 2021 Unit"]] = "kg/(cap*a)"
        if "Specific Waste Collected 2022" in index:
            row[index["Specific Waste Collected 2022"]] = 2022.0
        if "Specific Waste Collected 2022 Unit" in index:
            row[index["Specific Waste Collected 2022 Unit"]] = "t/a"
        if "Connection Rate 2024" in index:
            row[index["Connection Rate 2024"]] = 87.5
        if "Connection Rate 2024 Unit" in index:
            row[index["Connection Rate 2024 Unit"]] = "% residential properties"
        return row

    def test_row_layout_maps_improved_template_units_and_sources(self):
        header = [
            "Catchment",
            "NUTS/LAU Id",
            "Country",
            "Collector",
            "Collection System",
            "Waste Category",
            "Introduction of collection system (Year)",
            "Change of specifics in the system (Year)",
            "Type of change",
            "Connection type",
            "Allowed Materials",
            "Forbidden Materials",
            "Fee System",
            "Frequency",
            "Minimum bin size (L)",
            "Minimum required specific bin capacity (L/reference unit)",
            "Reference unit for minimum required specific bin capacity",
            "Population 2020",
            "Population 2020 Unit",
            "Population 2021",
            "Population 2021 Unit",
            "Population 2022",
            "Population 2022 Unit",
            "Population 2023",
            "Population 2023 Unit",
            "Population 2024",
            "Population 2024 Unit",
            "Population Density 2020",
            "Population Density 2020 Unit",
            "Population Density 2021",
            "Population Density 2021 Unit",
            "Population Density 2022",
            "Population Density 2022 Unit",
            "Population Density 2023",
            "Population Density 2023 Unit",
            "Population Density 2024",
            "Population Density 2024 Unit",
            "Specific Waste Collected 2021",
            "Specific Waste Collected 2021 Unit",
            "Specific Waste Collected 2022",
            "Specific Waste Collected 2022 Unit",
            "Connection Rate 2024",
            "Connection Rate 2024 Unit",
            "Comments",
            "Sources_new",
            "Weblinks",
            "Bibliography Sources",
            "Valid from",
            "Valid until",
        ]
        warnings = []
        header_index = import_de_2024_improved_standalone._build_header_index(header)
        record = import_de_2024_improved_standalone._row_to_record(
            self._build_row(header),
            header_index,
            row_label="row 2",
            warnings=warnings,
        )

        self.assertEqual(record["description"], "Updated import description")
        self.assertEqual(record["established"], 1998)
        self.assertEqual(record["valid_from"], "2024-01-01")
        self.assertIsNone(record["valid_until"])
        self.assertEqual(
            record["sources"],
            [
                "Personal communication with district office",
                "District annual report 2024",
            ],
        )
        self.assertEqual(
            record["flyer_urls"],
            [
                "https://example.com/a.pdf",
                "https://example.com/b.pdf",
                "https://example.com/archive.pdf",
            ],
        )
        self.assertEqual(
            record["property_values"],
            [
                {
                    "property_id": import_de_2024_improved_standalone._PROP_CONN_RATE,
                    "unit_name": "% of residential properties",
                    "year": 2024,
                    "average": 87.5,
                },
                {
                    "property_id": import_de_2024_improved_standalone._PROP_SPECIFIC,
                    "unit_name": import_de_2024_improved_standalone._UNIT_KG,
                    "year": 2021,
                    "average": 21.0,
                },
                {
                    "property_id": import_de_2024_improved_standalone._PROP_TOTAL,
                    "unit_name": import_de_2024_improved_standalone._UNIT_MG,
                    "year": 2022,
                    "average": 2022.0,
                },
            ],
        )
        self.assertEqual(warnings, [])

    def test_row_layout_supports_sachsen_anhalt_variant(self):
        header = [
            "Catchment",
            "NUTS/LAU Id",
            "Country",
            "Collector",
            "Collection System",
            "Waste Category",
            "Introduction of collection system (Year)",
            "Change of specifics in the system (Year)",
            "Type of change",
            "Connection type",
            "Allowed Materials",
            "Forbidden Materials",
            "Fee System",
            "Frequency",
            "Minimum bin size (L)",
            "Minimum required specific bin capacity (L/reference unit)",
            "Reference unit for minimum required specific bin capacity",
            "Population 2020",
            "Population 2020 Unit",
            "Population 2021",
            "Population 2021 Unit",
            "Population 2022",
            "Population 2022 Unit",
            "Population 2023",
            "Population 2023 Unit",
            "Population 2024",
            "Population 2024 Unit",
            "Population Density 2021",
            "Population Density 2021 Unit",
            "Population Density 2022",
            "Population Density 2022 Unit",
            "Population Density 2023",
            "Population Density 2023 Unit",
            "Population Density 2024",
            "Population Density 2024 Unit",
            "Specific Waste Collected 2021",
            "Specific Waste Collected 2021 Unit",
            "Specific Waste Collected 2022",
            "Specific Waste Collected 2022 Unit",
            "Connection Rate 2024",
            "Connection Rate 2024 Unit",
            "Comments",
            "Weblinks",
            "Sources_new",
            "Valid from",
            "Valid until",
        ]
        warnings = []
        header_index = import_de_2024_improved_standalone._build_header_index(header)
        row = self._build_row(header)
        row[header.index("Specific Waste Collected 2021 Unit")] = "t/a"
        record = import_de_2024_improved_standalone._row_to_record(
            row,
            header_index,
            row_label="row 2",
            warnings=warnings,
        )

        self.assertEqual(
            record["sources"], ["Personal communication with district office"]
        )
        self.assertEqual(
            record["flyer_urls"],
            [
                "https://example.com/a.pdf",
                "https://example.com/b.pdf",
                "https://example.com/archive.pdf",
            ],
        )
        self.assertEqual(
            record["property_values"][1],
            {
                "property_id": import_de_2024_improved_standalone._PROP_TOTAL,
                "unit_name": import_de_2024_improved_standalone._UNIT_MG,
                "year": 2021,
                "average": 21.0,
            },
        )
        self.assertEqual(warnings, [])

    def test_unknown_amount_unit_is_skipped_with_warning(self):
        header = [
            "Catchment",
            "NUTS/LAU Id",
            "Collector",
            "Collection System",
            "Waste Category",
            "Introduction of collection system (Year)",
            "Connection type",
            "Allowed Materials",
            "Forbidden Materials",
            "Fee System",
            "Frequency",
            "Minimum bin size (L)",
            "Minimum required specific bin capacity (L/reference unit)",
            "Reference unit for minimum required specific bin capacity",
            "Comments",
            "Sources_new",
            "Weblinks",
            "Valid from",
            "Specific Waste Collected 2024",
            "Specific Waste Collected 2024 Unit",
        ]
        warnings = []
        header_index = import_de_2024_improved_standalone._build_header_index(header)
        row = self._build_row(header)
        row[header.index("Specific Waste Collected 2024")] = 1.5
        row[header.index("Specific Waste Collected 2024 Unit")] = "unknown-unit"
        record = import_de_2024_improved_standalone._row_to_record(
            row,
            header_index,
            row_label="workbook row 9",
            warnings=warnings,
        )

        self.assertEqual(record["property_values"], [])
        self.assertEqual(
            warnings,
            [
                "workbook row 9: skipped Specific Waste Collected 2024 because unit 'unknown-unit' is not supported."
            ],
        )
