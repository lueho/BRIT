"""Tests for the Catalonia 2024 collection import command."""

from django.test import SimpleTestCase

from sources.waste_collection.management.commands import (
    import_catalonia_2024_collections as cmd,
)


def _make_row(
    *,
    codi="080018",
    collector="",
    waste_type="Biowaste",
    collection_system="PAP Total",
    conn_rate_2024=100,
    frequency="Fixed; 156 per year (3 per week)",
    fee_system="no payt",
    min_bin_size=None,
    qty_2024_t=530.86,
    qty_2024_kg_per_cap=87.73,
    qty_2020_t=624.98,
    qty_2020_kg_per_cap=108.47,
    impurities_2024=None,
    comments=None,
    change_impl=None,
    change_year=None,
    sources="https://example.com/source.pdf",
) -> tuple:
    """Build a minimal row tuple matching the Catalonia Excel column layout."""
    row = [None] * 31
    row[0] = "Barcelona"  # nuts3_name
    row[1] = "Bages"  # comarca
    row[2] = codi  # codi
    row[3] = "Test Municipality"
    row[4] = collector  # Collector
    row[5] = 5762  # població_2020
    row[6] = 6051  # població_2024
    row[7] = None  # formula ratio
    row[8] = "17.87"  # superfície
    row[9] = "316"  # altitud
    row[10] = waste_type  # Waste type
    row[11] = None  # PaP_status_2020
    row[12] = None  # porta.a.porta_2024
    row[13] = collection_system  # Collection_system_2024
    row[14] = "no"  # Access control
    row[15] = None  # Connection rate 2020
    row[16] = conn_rate_2024  # Connection rate 2024
    row[17] = frequency  # Collection frequency
    row[18] = None  # Weekly access days_BP
    row[19] = fee_system  # Fee system
    row[20] = min_bin_size  # Minimum bin size (L)
    row[21] = change_impl  # Change implementation
    row[22] = change_year  # Change implementation year
    row[23] = qty_2020_t  # Quantity_2020_t
    row[24] = qty_2020_kg_per_cap  # Quantity_2020_kg (data_only result)
    row[25] = qty_2024_t  # Quantity_2024_t
    row[26] = qty_2024_kg_per_cap  # Quantity_2024_kg (data_only result)
    row[27] = None  # Impurities_percentge_2020
    row[28] = impurities_2024  # Impurities_percentage 2024
    row[29] = comments  # Comments
    row[30] = sources  # Sources
    return tuple(row)


class IneToLauTests(SimpleTestCase):
    """Tests for the INE-code → Eurostat LAU ID conversion."""

    def test_barcelona_province(self):
        self.assertEqual(cmd._ine_to_lau("080018"), "08001")

    def test_girona_province(self):
        self.assertEqual(cmd._ine_to_lau("170010"), "17001")

    def test_lleida_province(self):
        self.assertEqual(cmd._ine_to_lau("250019"), "25001")

    def test_tarragona_province(self):
        self.assertEqual(cmd._ine_to_lau("430017"), "43001")

    def test_known_mapping_abrera(self):
        # Excel 080018 → LAU 08001 (Abrera)
        self.assertEqual(cmd._ine_to_lau("080018"), "08001")

    def test_known_mapping_artes(self):
        # Excel 080109 → LAU 08010 (Artés)
        self.assertEqual(cmd._ine_to_lau("080109"), "08010")

    def test_none_returns_empty(self):
        self.assertEqual(cmd._ine_to_lau(None), "")

    def test_short_code_returns_empty(self):
        self.assertEqual(cmd._ine_to_lau("0800"), "")

    def test_exact_five_chars(self):
        self.assertEqual(cmd._ine_to_lau("08001"), "08001")


class CollectionSystemMappingTests(SimpleTestCase):
    """Tests for the collection system lookup."""

    def test_pap_total_maps_to_door_to_door(self):
        self.assertEqual(
            cmd._map_collection_system("PAP Total", "Biowaste"), "Door to door"
        )

    def test_pap_total_case_insensitive(self):
        self.assertEqual(
            cmd._map_collection_system("pap total", "Biowaste"), "Door to door"
        )
        self.assertEqual(
            cmd._map_collection_system("PAP total", "Biowaste"), "Door to door"
        )

    def test_pap_total_pxg_maps_to_door_to_door(self):
        self.assertEqual(
            cmd._map_collection_system("PAP Total + PxG", "Biowaste"),
            "Door to door",
        )

    def test_pap_parcial_maps_to_mixed(self):
        self.assertEqual(
            cmd._map_collection_system("PAP parcial", "Biowaste"),
            cmd._CS_MIXED_DT_BP,
        )

    def test_pap_parcial_case_variant_maps_to_mixed(self):
        self.assertEqual(
            cmd._map_collection_system("PAP Parcial", "Biowaste"),
            cmd._CS_MIXED_DT_BP,
        )

    def test_community_composting_maps_to_no_separate_collection(self):
        self.assertEqual(
            cmd._map_collection_system("Community composting", "Biowaste"),
            "No separate collection",
        )

    def test_planned_pap_maps_to_empty_string(self):
        self.assertEqual(
            cmd._map_collection_system("Propera implantació PAP", "Biowaste"), ""
        )

    def test_bring_point_maps_to_bring_point(self):
        self.assertEqual(
            cmd._map_collection_system("Bring point", "Biowaste"), "Bring point"
        )

    def test_no_separate_collection(self):
        self.assertEqual(
            cmd._map_collection_system("No separate collection", "Biowaste"),
            "No separate collection",
        )

    def test_no_pap_category(self):
        self.assertEqual(
            cmd._map_collection_system(
                "No PaP category / not shown as PaP", "Biowaste"
            ),
            "No separate collection",
        )

    def test_recycling_centre(self):
        self.assertEqual(
            cmd._map_collection_system("Recycling centre", "Biowaste"),
            "Recycling centre",
        )

    def test_residual_waste_with_null_defaults_to_door_to_door(self):
        self.assertEqual(
            cmd._map_collection_system(None, "Residual waste"), "Door to door"
        )

    def test_unknown_biowaste_system_returns_empty(self):
        self.assertEqual(cmd._map_collection_system("Unknown system", "Biowaste"), "")


class FeeSystemMappingTests(SimpleTestCase):
    def test_payt_canonical(self):
        self.assertEqual(
            cmd._map_fee_system("Pay as you throw (PAYT)"),
            "Pay as you throw (PAYT)",
        )

    def test_pxg(self):
        self.assertEqual(cmd._map_fee_system("PxG"), "Pay as you throw (PAYT)")

    def test_basic_fee(self):
        self.assertEqual(cmd._map_fee_system("Basic fee"), "Flat fee")

    def test_no_fee(self):
        self.assertEqual(cmd._map_fee_system("No fee"), "No fee")

    def test_no_payt_variants(self):
        for raw in ("no payt", "no Payt", "no PAYT"):
            with self.subTest(raw=raw):
                self.assertEqual(cmd._map_fee_system(raw), "Flat fee")

    def test_none_returns_empty(self):
        self.assertEqual(cmd._map_fee_system(None), "")

    def test_unknown_returns_empty(self):
        self.assertEqual(cmd._map_fee_system("unknown fee"), "")


class RowToRecordBiowasteTests(SimpleTestCase):
    """Tests for _row_to_record with Biowaste rows."""

    def _record(self, **kwargs) -> dict:
        row = _make_row(**kwargs)
        return cmd._row_to_record(row)

    def test_returns_dict_for_valid_biowaste_row(self):
        record = self._record()
        self.assertIsNotNone(record)
        self.assertIsInstance(record, dict)

    def test_lau_id_derived_from_codi(self):
        record = self._record(codi="080109")
        self.assertEqual(record["nuts_or_lau_id"], "08010")

    def test_country_code_is_es(self):
        record = self._record()
        self.assertEqual(record["country_code"], "ES")

    def test_catchment_name_empty(self):
        record = self._record()
        self.assertEqual(record["catchment_name"], "")

    def test_waste_category_biowaste(self):
        record = self._record()
        self.assertEqual(record["waste_category"], "Biowaste")

    def test_collection_system_pap_total(self):
        record = self._record(collection_system="PAP Total")
        self.assertEqual(record["collection_system"], "Door to door")

    def test_collection_system_bring_point(self):
        record = self._record(collection_system="Bring point")
        self.assertEqual(record["collection_system"], "Bring point")

    def test_collection_system_pap_parcial_is_mixed(self):
        record = self._record(collection_system="PAP parcial")
        self.assertEqual(record["collection_system"], cmd._CS_MIXED_DT_BP)

    def test_collection_system_planned_pap_is_empty(self):
        record = self._record(collection_system="Propera implantació PAP")
        self.assertEqual(record["collection_system"], "")

    def test_fee_system_no_payt(self):
        record = self._record(fee_system="no payt")
        self.assertEqual(record["fee_system"], "Flat fee")

    def test_fee_system_payt(self):
        record = self._record(fee_system="Pay as you throw (PAYT)")
        self.assertEqual(record["fee_system"], "Pay as you throw (PAYT)")

    def test_frequency_preserved(self):
        record = self._record(frequency="Fixed; 104 per year (2 per week)")
        self.assertEqual(record["frequency"], "Fixed; 104 per year (2 per week)")

    def test_clear_frequency_for_update_2_removed_frequency_row(self):
        record = self._record(codi="170059", frequency=None)
        self.assertEqual(record["frequency"], "")
        self.assertIs(record["clear_frequency"], True)

    def test_blank_frequency_does_not_clear_unlisted_rows(self):
        record = self._record(codi="080018", frequency=None)
        self.assertEqual(record["frequency"], "")
        self.assertIs(record["clear_frequency"], False)

    def test_valid_from_is_2024_01_01(self):
        record = self._record()
        self.assertEqual(record["valid_from"], "2024-01-01")

    def test_valid_until_is_open_ended(self):
        record = self._record()
        self.assertIsNone(record["valid_until"])

    def test_property_values_contain_specific_2024(self):
        record = self._record(qty_2024_kg_per_cap=87.73, qty_2024_t=530.86)
        pvs = record["property_values"]
        specific = [
            p
            for p in pvs
            if p["property_id"] == cmd._PROP_SPECIFIC and p["year"] == 2024
        ]
        self.assertEqual(len(specific), 1)
        self.assertAlmostEqual(specific[0]["average"], 87.73, places=2)
        self.assertEqual(specific[0]["unit_name"], cmd._UNIT_KG)

    def test_property_values_contain_total_2024(self):
        record = self._record(qty_2024_t=530.86)
        pvs = record["property_values"]
        total = [
            p for p in pvs if p["property_id"] == cmd._PROP_TOTAL and p["year"] == 2024
        ]
        self.assertEqual(len(total), 1)
        self.assertAlmostEqual(total[0]["average"], 530.86, places=2)
        self.assertEqual(total[0]["unit_name"], cmd._UNIT_MG)

    def test_property_values_contain_specific_2020(self):
        record = self._record(qty_2020_kg_per_cap=108.47)
        pvs = record["property_values"]
        specific_2020 = [
            p
            for p in pvs
            if p["property_id"] == cmd._PROP_SPECIFIC and p["year"] == 2020
        ]
        self.assertEqual(len(specific_2020), 1)
        self.assertAlmostEqual(specific_2020[0]["average"], 108.47, places=2)

    def test_property_values_contain_total_2020(self):
        record = self._record(qty_2020_t=624.98)
        pvs = record["property_values"]
        total_2020 = [
            p for p in pvs if p["property_id"] == cmd._PROP_TOTAL and p["year"] == 2020
        ]
        self.assertEqual(len(total_2020), 1)
        self.assertAlmostEqual(total_2020[0]["average"], 624.98, places=2)

    def test_connection_rate_2024_included_for_biowaste(self):
        record = self._record(conn_rate_2024=100)
        pvs = record["property_values"]
        conn = [p for p in pvs if p["property_id"] == cmd._PROP_CONN_RATE]
        self.assertEqual(len(conn), 1)
        self.assertEqual(conn[0]["average"], 100.0)
        self.assertEqual(conn[0]["unit_name"], cmd._UNIT_PCT_HH)

    def test_zero_qty_not_included_in_property_values(self):
        record = self._record(qty_2024_t=0, qty_2024_kg_per_cap=0)
        pvs = record["property_values"]
        specific_2024 = [
            p
            for p in pvs
            if p["property_id"] == cmd._PROP_SPECIFIC and p["year"] == 2024
        ]
        total_2024 = [
            p for p in pvs if p["property_id"] == cmd._PROP_TOTAL and p["year"] == 2024
        ]
        self.assertEqual(len(specific_2024), 0)
        self.assertEqual(len(total_2024), 0)

    def test_none_qty_not_included(self):
        record = self._record(qty_2024_t=None, qty_2024_kg_per_cap=None)
        pvs = record["property_values"]
        specific_2024 = [
            p
            for p in pvs
            if p["property_id"] == cmd._PROP_SPECIFIC and p["year"] == 2024
        ]
        self.assertEqual(len(specific_2024), 0)

    def test_source_url_in_flyer_urls(self):
        record = self._record(sources="https://example.com/source.pdf")
        self.assertIn("https://example.com/source.pdf", record["flyer_urls"])

    def test_multiple_source_urls_extracted(self):
        record = self._record(
            sources="https://example.com/a.pdf, https://example.com/b.pdf"
        )
        self.assertIn("https://example.com/a.pdf", record["flyer_urls"])
        self.assertIn("https://example.com/b.pdf", record["flyer_urls"])

    def test_no_source_url_falls_back_to_dataset_url(self):
        record = self._record(sources=None)
        self.assertEqual(record["flyer_urls"], [cmd._SOURCE_URL])

    def test_collector_preserved(self):
        record = self._record(collector="Anoiaverda")
        self.assertEqual(record["collector_name"], "Anoiaverda")

    def test_empty_collector_preserved(self):
        record = self._record(collector="")
        self.assertEqual(record["collector_name"], "")

    def test_comments_in_description(self):
        record = self._record(comments="Community composting")
        self.assertIn("Community composting", record["description"])

    def test_change_implementation_in_description(self):
        record = self._record(change_impl="PAP", change_year=2014)
        self.assertIn("PAP", record["description"])
        self.assertIn("2014", record["description"])

    def test_description_empty_when_no_comments_or_change(self):
        record = self._record(comments=None, change_impl=None)
        self.assertEqual(
            record["description"],
            "Catalonia 2024 source collection system: PAP total",
        )

    def test_raw_catalonia_collection_system_in_description(self):
        record = self._record(collection_system="PAP Parcial")
        self.assertIn(
            "Catalonia 2024 source collection system: PAP parcial",
            record["description"],
        )

    def test_updated_layout_dict_uses_header_names(self):
        row = {
            "codi": "080023",
            "municipi": "Aguilar de Segarra",
            "Collector": "Consorci del Bages per a la Gestió de Residus",
            "Waste type": "Biowaste",
            "Collection_system_2024": "Bring point",
            "access_control": "yes",
            "Connection rate to PaP_2024": 100,
            "Collection frequency": "",
            "Fee system": "",
            "Minimum bin size (L)": None,
            "Change implementation": "Access control",
            "Change implementation year": 2022,
            "Quantity_2020_t": 0,
            "Quantity_2020_kg": 0,
            "Quantity_2024_t": 29.33,
            "Quantity_2024_kg": 100.79037800687286,
            "Comments": None,
            "Sources": "https://example.com/source.pdf",
        }
        record = cmd._row_to_record(row)

        self.assertEqual(record["collection_system"], "Bring point")
        self.assertIs(record["access_control_bp"], True)
        self.assertIsNone(record["access_control_pap"])
        self.assertIn(
            "Catalonia 2024 source collection system: Bring point",
            record["description"],
        )

    def test_returns_none_for_unknown_waste_type(self):
        row = _make_row()
        row = list(row)
        row[10] = "Glass"
        record = cmd._row_to_record(tuple(row))
        self.assertIsNone(record)

    def test_returns_none_for_missing_codi(self):
        row = list(_make_row())
        row[2] = None
        record = cmd._row_to_record(tuple(row))
        self.assertIsNone(record)


class RowToRecordResidualWasteTests(SimpleTestCase):
    """Tests for _row_to_record with Residual waste rows."""

    def _record(self, **kwargs) -> dict:
        kwargs.setdefault("waste_type", "Residual waste")
        kwargs.setdefault("collection_system", None)
        kwargs.setdefault("conn_rate_2024", None)
        kwargs.setdefault("frequency", "Fixed; 52 per year (1 per week)")
        row = _make_row(**kwargs)
        return cmd._row_to_record(row)

    def test_residual_waste_defaults_to_door_to_door(self):
        record = self._record()
        self.assertEqual(record["collection_system"], "Door to door")

    def test_waste_category_is_residual(self):
        record = self._record()
        self.assertEqual(record["waste_category"], "Residual waste")

    def test_no_connection_rate_for_residual(self):
        record = self._record()
        pvs = record["property_values"]
        conn = [p for p in pvs if p["property_id"] == cmd._PROP_CONN_RATE]
        self.assertEqual(len(conn), 0)

    def test_specific_and_total_2024_included(self):
        record = self._record(qty_2024_t=722.8, qty_2024_kg_per_cap=119.45)
        pvs = record["property_values"]
        specific = [
            p
            for p in pvs
            if p["property_id"] == cmd._PROP_SPECIFIC and p["year"] == 2024
        ]
        total = [
            p for p in pvs if p["property_id"] == cmd._PROP_TOTAL and p["year"] == 2024
        ]
        self.assertEqual(len(specific), 1)
        self.assertEqual(len(total), 1)


class SplitSourceCellTests(SimpleTestCase):
    def test_single_url(self):
        urls, notes = cmd._split_source_cell("https://example.com/doc.pdf")
        self.assertEqual(urls, ["https://example.com/doc.pdf"])
        self.assertEqual(notes, [])

    def test_multiple_urls(self):
        urls, notes = cmd._split_source_cell(
            "https://example.com/a.pdf, https://example.com/b.pdf"
        )
        self.assertIn("https://example.com/a.pdf", urls)
        self.assertIn("https://example.com/b.pdf", urls)
        self.assertEqual(notes, [])

    def test_mixed_url_and_text(self):
        urls, notes = cmd._split_source_cell(
            "https://example.com/a.pdf, some note text"
        )
        self.assertEqual(urls, ["https://example.com/a.pdf"])
        self.assertEqual(notes, ["some note text"])

    def test_empty_returns_empty(self):
        urls, notes = cmd._split_source_cell("")
        self.assertEqual(urls, [])
        self.assertEqual(notes, [])

    def test_none_returns_empty(self):
        urls, notes = cmd._split_source_cell(None)
        self.assertEqual(urls, [])
        self.assertEqual(notes, [])

    def test_space_separated_urls_are_split(self):
        # Two URLs separated by a space (not a comma) must each be a separate entry.
        raw = "https://example.com/a.pdf https://example.com/b.pdf"
        urls, notes = cmd._split_source_cell(raw)
        self.assertEqual(
            urls, ["https://example.com/a.pdf", "https://example.com/b.pdf"]
        )
        self.assertEqual(notes, [])

    def test_webarchive_url_not_split_at_inner_https(self):
        # A web.archive.org URL embeds the original URL after the timestamp —
        # the inner https:// must NOT cause a split.
        raw = (
            "https://example.com/doc.pdf "
            "https://web.archive.org/web/20240712210145/"
            "https://example.com/original/"
        )
        urls, notes = cmd._split_source_cell(raw)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://example.com/doc.pdf")
        self.assertIn("web.archive.org", urls[1])
        self.assertIn("https://example.com/original/", urls[1])

    def test_partial_scheme_ttps_is_repaired(self):
        # "ttps://…" missing leading 'h' must be repaired and added to flyer_urls,
        # not stored as a plain text note (which would crash on Source.title max_length).
        raw = "ttps://example.com/some-very-long-path-that-exceeds-50-characters"
        urls, notes = cmd._split_source_cell(raw)
        self.assertEqual(len(urls), 1)
        self.assertTrue(urls[0].startswith("https://"))
        self.assertEqual(notes, [])

    def test_change_year_string_in_description(self):
        # Change year value like '2025/2026' must not crash row parsing.
        row = list(_make_row())
        row[21] = "PAP"
        row[22] = "2025/2026"
        record = cmd._row_to_record(tuple(row))
        self.assertIsNotNone(record)
        self.assertIn("2025/2026", record["description"])


class AccessControlMappingTests(SimpleTestCase):
    """Tests for _map_access_control and _access_control_fields."""

    # --- _parse_yes_no --------------------------------------------------

    def test_parse_yes(self):
        self.assertIs(cmd._parse_yes_no("yes"), True)

    def test_parse_no(self):
        self.assertIs(cmd._parse_yes_no("no"), False)

    def test_parse_case_insensitive(self):
        self.assertIs(cmd._parse_yes_no("YES"), True)
        self.assertIs(cmd._parse_yes_no("No"), False)

    def test_parse_unknown_returns_none(self):
        self.assertIsNone(cmd._parse_yes_no("maybe"))

    # --- _map_access_control returns (bp, pap) tuple -------------------

    def test_none_returns_none_tuple(self):
        self.assertEqual(cmd._map_access_control(None), (None, None))

    def test_single_yes_returns_yes_in_bp_slot(self):
        # Single value → bp slot carries value, pap = None
        bp, pap = cmd._map_access_control("yes")
        self.assertIs(bp, True)
        self.assertIsNone(pap)

    def test_single_no_returns_no_in_bp_slot(self):
        bp, pap = cmd._map_access_control("no")
        self.assertIs(bp, False)
        self.assertIsNone(pap)

    def test_slash_yes_no_bp_yes_pap_no(self):
        # BP/PAP order → 'yes/no' → bp=True, pap=False
        bp, pap = cmd._map_access_control("yes/no")
        self.assertIs(bp, True)
        self.assertIs(pap, False)

    def test_slash_no_yes_bp_no_pap_yes(self):
        bp, pap = cmd._map_access_control("no/yes")
        self.assertIs(bp, False)
        self.assertIs(pap, True)

    def test_slash_yes_yes_both_true(self):
        bp, pap = cmd._map_access_control("yes/yes")
        self.assertIs(bp, True)
        self.assertIs(pap, True)

    def test_slash_no_no_both_false(self):
        bp, pap = cmd._map_access_control("no/no")
        self.assertIs(bp, False)
        self.assertIs(pap, False)

    # --- _access_control_fields routing ---------------------------------

    def test_single_yes_on_bring_point_row_routes_to_bp(self):
        fields = cmd._access_control_fields("yes", cmd._CS_BRING_POINT)
        self.assertIs(fields["access_control_bp"], True)
        self.assertIsNone(fields["access_control_pap"])

    def test_single_no_on_door_to_door_row_routes_to_pap(self):
        fields = cmd._access_control_fields("no", cmd._CS_DOOR_TO_DOOR)
        self.assertIsNone(fields["access_control_bp"])
        self.assertIs(fields["access_control_pap"], False)

    def test_single_value_on_other_system_both_none(self):
        fields = cmd._access_control_fields("yes", cmd._CS_NO_SEPARATE)
        self.assertIsNone(fields["access_control_bp"])
        self.assertIsNone(fields["access_control_pap"])

    def test_slash_value_fills_both_regardless_of_system(self):
        fields = cmd._access_control_fields("yes/no", cmd._CS_DOOR_TO_DOOR)
        self.assertIs(fields["access_control_bp"], True)
        self.assertIs(fields["access_control_pap"], False)

    def test_none_raw_both_none(self):
        fields = cmd._access_control_fields(None, cmd._CS_BRING_POINT)
        self.assertIsNone(fields["access_control_bp"])
        self.assertIsNone(fields["access_control_pap"])

    # --- _row_to_record integration -------------------------------------

    def test_row_to_record_pap_row_yes_sets_pap_field(self):
        # Default _make_row uses PAP Total → Door to door → single 'yes' → pap
        row = list(_make_row())
        row[14] = "yes"
        record = cmd._row_to_record(tuple(row))
        self.assertIsNone(record["access_control_bp"])
        self.assertIs(record["access_control_pap"], True)

    def test_row_to_record_bp_row_no_sets_bp_field(self):
        row = list(_make_row(collection_system="Bring point"))
        row[14] = "no"
        record = cmd._row_to_record(tuple(row))
        self.assertIs(record["access_control_bp"], False)
        self.assertIsNone(record["access_control_pap"])

    def test_row_to_record_pap_parcial_slash_sets_both(self):
        row = list(_make_row(collection_system="PAP parcial"))
        row[14] = "yes/no"
        record = cmd._row_to_record(tuple(row))
        self.assertIs(record["access_control_bp"], True)
        self.assertIs(record["access_control_pap"], False)

    def test_row_to_record_none_access_control(self):
        row = list(_make_row())
        row[14] = None
        record = cmd._row_to_record(tuple(row))
        self.assertIsNone(record["access_control_bp"])
        self.assertIsNone(record["access_control_pap"])


class FrequencyNormalisationTests(SimpleTestCase):
    """Tests for _normalise_frequency."""

    def test_xx_per_year_mapped_to_canonical(self):
        raw = (
            "Fixed-Seasonal; xx per year "
            "(2 per week from October - April, 3 per week from May - September)"
        )
        expected = (
            "Fixed-Seasonal; October-April 61 per year; May-September 66 per year"
        )
        self.assertEqual(cmd._normalise_frequency(raw), expected)

    def test_205_per_year_mapped_to_canonical(self):
        raw = (
            "Fixed-Seasonal; 205 per year "
            "(3 per week from October - June and 7 per week from July - September)"
        )
        expected = (
            "Fixed-Seasonal; October-June 117 per year; July-September 88 per year"
        )
        self.assertEqual(cmd._normalise_frequency(raw), expected)

    def test_165_per_year_mapped_to_canonical(self):
        raw = (
            "Fixed-Seasonal; 165 per year "
            "(3 per week from September - June, 4 per week from July - August)"
        )
        expected = (
            "Fixed-Seasonal; September-June 130 per year; July-August 35 per year"
        )
        self.assertEqual(cmd._normalise_frequency(raw), expected)

    def test_169_per_year_mapped_to_canonical(self):
        raw = (
            "Fixed-Seasonal; 169 per year "
            "(3 per week from mid September - mid June "
            "& 4 per week from mid June - mid September)"
        )
        expected = (
            "Fixed-Seasonal; September-June 130 per year; June-September 39 per year"
        )
        self.assertEqual(cmd._normalise_frequency(raw), expected)

    def test_known_frequency_passes_through_unchanged(self):
        raw = "Fixed; 104 per year (2 per week)"
        self.assertEqual(cmd._normalise_frequency(raw), raw)

    def test_empty_string_passes_through(self):
        self.assertEqual(cmd._normalise_frequency(""), "")

    def test_row_to_record_applies_normalisation(self):
        # Confirm the normalisation is applied when building a record.
        raw_freq = (
            "Fixed-Seasonal; xx per year "
            "(2 per week from October - April, 3 per week from May - September)"
        )
        row = list(_make_row(frequency=raw_freq))
        record = cmd._row_to_record(tuple(row))
        self.assertIsNotNone(record)
        self.assertEqual(
            record["frequency"],
            "Fixed-Seasonal; October-April 61 per year; May-September 66 per year",
        )


class RowTo2020RecordTests(SimpleTestCase):
    """Tests for _row_to_2020_record (issue #113: 2020 collection-system data)."""

    def _make_row_with_2020(self, pap_status_2020=None, **kwargs):
        row = list(_make_row(**kwargs))
        row[11] = pap_status_2020  # PaP_status_2020
        return tuple(row)

    def test_returns_dict_when_2020_system_known(self):
        row = self._make_row_with_2020(pap_status_2020="PAP Total")
        record = cmd._row_to_2020_record(row)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, dict)

    def test_valid_from_is_2020(self):
        row = self._make_row_with_2020(pap_status_2020="PAP Total")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["valid_from"], "2020-01-01")

    def test_valid_until_is_2023(self):
        row = self._make_row_with_2020(pap_status_2020="PAP Total")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["valid_until"], "2023-12-31")

    def test_collection_system_pap_total_maps_to_door_to_door(self):
        row = self._make_row_with_2020(pap_status_2020="PAP Total")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["collection_system"], "Door to door")

    def test_collection_system_bring_point_2020(self):
        row = self._make_row_with_2020(pap_status_2020="Bring point")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["collection_system"], "Bring point")

    def test_collection_system_pap_parcial_is_mixed_for_2020(self):
        row = self._make_row_with_2020(pap_status_2020="PAP parcial")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["collection_system"], cmd._CS_MIXED_DT_BP)

    def test_returns_none_when_2020_system_empty(self):
        row = self._make_row_with_2020(pap_status_2020=None)
        record = cmd._row_to_2020_record(row)
        self.assertIsNone(record)

    def test_returns_none_when_2020_system_unknown(self):
        row = self._make_row_with_2020(pap_status_2020="Propera implantació PAP")
        record = cmd._row_to_2020_record(row)
        self.assertIsNone(record)

    def test_residual_waste_defaults_to_door_to_door_when_system_empty(self):
        row = list(
            self._make_row_with_2020(
                waste_type="Residual waste",
                collection_system=None,
                pap_status_2020=None,
            )
        )
        # Residual rows default to Door to door even with empty PaP_status_2020
        record = cmd._row_to_2020_record(tuple(row))
        self.assertIsNotNone(record)
        self.assertEqual(record["collection_system"], "Door to door")

    def test_property_values_empty_for_2020_record(self):
        row = self._make_row_with_2020(pap_status_2020="PAP Total")
        record = cmd._row_to_2020_record(row)
        self.assertEqual(record["property_values"], [])

    def test_returns_none_for_missing_codi(self):
        row = list(self._make_row_with_2020(pap_status_2020="PAP Total"))
        row[2] = None
        record = cmd._row_to_2020_record(tuple(row))
        self.assertIsNone(record)


class BiowasteImpurityPropertyTests(SimpleTestCase):
    """Tests for biowaste impurity rate property values emitted by _row_to_record."""

    def _pvs_by_property(self, record):
        """Return a dict mapping property_name → list of PV dicts."""
        result = {}
        for pv in record["property_values"]:
            key = pv.get("property_name") or pv.get("property_id")
            result.setdefault(key, []).append(pv)
        return result

    def test_impurity_2024_present_when_value_given(self):
        row = list(_make_row(impurities_2024=12.5))
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertIn(cmd._PROP_NAME_IMPURITY, pvs)
        impurity_pvs = pvs[cmd._PROP_NAME_IMPURITY]
        years = [pv["year"] for pv in impurity_pvs]
        self.assertIn(cmd._DATA_YEAR, years)

    def test_impurity_2024_value_rounded(self):
        row = list(_make_row(impurities_2024=12.5555))
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        impurity_pvs = pvs[cmd._PROP_NAME_IMPURITY]
        pv_2024 = next(pv for pv in impurity_pvs if pv["year"] == cmd._DATA_YEAR)
        self.assertEqual(pv_2024["average"], round(12.5555, 4))

    def test_impurity_2024_unit_is_percent(self):
        row = list(_make_row(impurities_2024=10.0))
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        impurity_pvs = pvs[cmd._PROP_NAME_IMPURITY]
        pv_2024 = next(pv for pv in impurity_pvs if pv["year"] == cmd._DATA_YEAR)
        self.assertEqual(pv_2024["unit_name"], cmd._UNIT_PCT)

    def test_impurity_2020_present_when_column_27_has_value(self):
        row = list(_make_row())
        row[27] = 8.3  # Impurities_percentge_2020
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertIn(cmd._PROP_NAME_IMPURITY, pvs)
        years = [pv["year"] for pv in pvs[cmd._PROP_NAME_IMPURITY]]
        self.assertIn(cmd._DATA_YEAR_2020, years)

    def test_impurity_absent_when_none(self):
        row = list(_make_row(impurities_2024=None))
        # Also ensure col 27 is None
        row[27] = None
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertNotIn(cmd._PROP_NAME_IMPURITY, pvs)

    def test_impurity_only_emitted_for_biowaste(self):
        row = list(_make_row(waste_type="Residual waste", impurities_2024=10.0))
        record = cmd._row_to_record(tuple(row))
        self.assertIsNotNone(record)
        pvs = self._pvs_by_property(record)
        self.assertNotIn(cmd._PROP_NAME_IMPURITY, pvs)


class WeeklyBpAccessDaysPropertyTests(SimpleTestCase):
    """Tests for weekly bring-point access days property values emitted by _row_to_record."""

    def _pvs_by_property(self, record):
        result = {}
        for pv in record["property_values"]:
            key = pv.get("property_name") or pv.get("property_id")
            result.setdefault(key, []).append(pv)
        return result

    def test_weekly_bp_present_for_bring_point_row(self):
        row = list(_make_row(collection_system="Bring point"))
        row[18] = 7.0  # Weekly access days_BP
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertIn(cmd._PROP_NAME_WEEKLY_BP_DAYS, pvs)

    def test_weekly_bp_present_for_mixed_row(self):
        row = list(_make_row(collection_system="PAP parcial"))
        row[18] = 3.0
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertIn(cmd._PROP_NAME_WEEKLY_BP_DAYS, pvs)

    def test_weekly_bp_absent_for_door_to_door(self):
        row = list(_make_row(collection_system="PAP Total"))
        row[18] = 7.0
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertNotIn(cmd._PROP_NAME_WEEKLY_BP_DAYS, pvs)

    def test_weekly_bp_absent_when_value_none(self):
        row = list(_make_row(collection_system="Bring point"))
        row[18] = None
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        self.assertNotIn(cmd._PROP_NAME_WEEKLY_BP_DAYS, pvs)

    def test_weekly_bp_unit_is_days_per_week(self):
        row = list(_make_row(collection_system="Bring point"))
        row[18] = 5.0
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        pv = pvs[cmd._PROP_NAME_WEEKLY_BP_DAYS][0]
        self.assertEqual(pv["unit_name"], cmd._UNIT_DAYS_PER_WK)

    def test_weekly_bp_value_rounded(self):
        row = list(_make_row(collection_system="Bring point"))
        row[18] = 4.55555
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        pv = pvs[cmd._PROP_NAME_WEEKLY_BP_DAYS][0]
        self.assertEqual(pv["average"], round(4.55555, 4))

    def test_weekly_bp_year_is_data_year(self):
        row = list(_make_row(collection_system="Bring point"))
        row[18] = 2.0
        record = cmd._row_to_record(tuple(row))
        pvs = self._pvs_by_property(record)
        pv = pvs[cmd._PROP_NAME_WEEKLY_BP_DAYS][0]
        self.assertEqual(pv["year"], cmd._DATA_YEAR)
