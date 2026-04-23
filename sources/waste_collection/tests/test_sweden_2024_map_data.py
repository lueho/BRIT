from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from sources.waste_collection.management.commands.import_sweden_collections import (
    _apply_2024_map_details,
)
from sources.waste_collection.sweden_2024_map_data import (
    MapAssignment,
    MapTransform,
    RawMapData,
    RawMapRow,
    build_prepared_row,
    load_map_details,
    load_map_import_details,
    load_prepared_map_details,
    load_raw_map_data,
    load_raw_map_details,
    load_reviewed_map_details,
    write_raw_map_data,
)


class Sweden2024MapDataHelpersTestCase(SimpleTestCase):
    def test_build_prepared_row_maps_clean_assignments_to_brit_values(self):
        row = build_prepared_row(
            lau_id="0180",
            municipality_name="Stockholm",
            sorting_assignment=MapAssignment(
                label="Separata kärl", classified_pixels=25, confidence=0.84
            ),
            bag_assignment=MapAssignment(
                label="Papper", classified_pixels=18, confidence=0.79
            ),
        )

        self.assertEqual(row["bin_configuration"], "Separate bins")
        self.assertEqual(row["bag_material"], "Collection Support Item: Paper bags")
        self.assertEqual(row["collection_system"], "Door to door")
        self.assertEqual(row["no_collection"], "0")
        self.assertEqual(row["needs_manual_review"], "0")

    def test_build_prepared_row_marks_no_collection_from_map_labels(self):
        row = build_prepared_row(
            lau_id="0180",
            municipality_name="Stockholm",
            sorting_assignment=MapAssignment(
                label="Ingen utsortering", classified_pixels=11, confidence=0.71
            ),
            bag_assignment=MapAssignment(
                label="ET", classified_pixels=9, confidence=0.73
            ),
        )

        self.assertEqual(row["collection_system"], "No separate collection")
        self.assertEqual(row["bin_configuration"], "")
        self.assertEqual(row["bag_material"], "")
        self.assertEqual(row["no_collection"], "1")
        self.assertEqual(row["needs_manual_review"], "0")

    def test_build_prepared_row_flags_bag_et_against_real_sorting_system(self):
        row = build_prepared_row(
            lau_id="0580",
            municipality_name="Linköping",
            sorting_assignment=MapAssignment(
                label="Fyrfackskärl", classified_pixels=22, confidence=1.0
            ),
            bag_assignment=MapAssignment(
                label="ET", classified_pixels=327, confidence=0.706
            ),
        )

        self.assertEqual(row["no_collection"], "1")
        self.assertEqual(row["needs_manual_review"], "1")
        self.assertIn("bag ET disagrees with sorting map", row["review_reasons"])

    def test_build_prepared_row_flags_inconsistent_map_pair_for_review(self):
        row = build_prepared_row(
            lau_id="0180",
            municipality_name="Stockholm",
            sorting_assignment=MapAssignment(
                label="ET", classified_pixels=10, confidence=0.83
            ),
            bag_assignment=MapAssignment(
                label="Papper", classified_pixels=8, confidence=0.77
            ),
        )

        self.assertEqual(row["no_collection"], "1")
        self.assertEqual(row["needs_manual_review"], "1")
        self.assertIn("sorting ET disagrees with bag map", row["review_reasons"])

    def test_load_prepared_map_details_ignores_manual_review_rows(self):
        with NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(
                "lau_id,municipality_name,sorting_label,bin_configuration,sorting_confidence,sorting_pixels,bag_label,bag_material,bag_confidence,bag_pixels,collection_system,no_collection,needs_manual_review,review_reasons\n"
            )
            handle.write(
                "0180,Stockholm,Separata kärl,Separate bins,0.88,12,Papper,Collection Support Item: Paper bags,0.80,10,Door to door,0,0,\n"
            )
            handle.write(
                "0181,Södertälje,ET,,0.71,7,ET,,0.69,7,No separate collection,1,1,needs review\n"
            )
            csv_path = Path(handle.name)
        self.addCleanup(csv_path.unlink)

        details = load_prepared_map_details(csv_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                }
            },
        )

    def test_load_map_import_details_includes_manual_review_metadata(self):
        with NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(
                "lau_id,municipality_name,sorting_label,bin_configuration,sorting_confidence,sorting_pixels,bag_label,bag_material,bag_confidence,bag_pixels,collection_system,no_collection,needs_manual_review,review_reasons\n"
            )
            handle.write(
                "0180,Stockholm,Separata kärl,Separate bins,0.88,12,Papper,Collection Support Item: Paper bags,0.80,10,Door to door,0,0,\n"
            )
            handle.write(
                "0181,Södertälje,ET,,0.71,7,ET,,0.69,7,No separate collection,1,1,bag ET disagrees with sorting map\n"
            )
            csv_path = Path(handle.name)
        self.addCleanup(csv_path.unlink)

        details = load_map_import_details(csv_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                    "needs_manual_review": False,
                    "review_reasons": [],
                },
                "0181": {
                    "no_collection": True,
                    "bin_configuration": None,
                    "bag_material": None,
                    "needs_manual_review": True,
                    "review_reasons": ["bag ET disagrees with sorting map"],
                },
            },
        )

    def test_load_raw_map_details_prefers_reviewed_json_fields(self):
        payload = {
            "format": "sweden-2024-map-raw",
            "version": 1,
            "left_transform": {
                "scale_multiplier": 0.97,
                "dx": 0,
                "dy": 0,
                "assigned_count": 283,
            },
            "right_transform": {
                "scale_multiplier": 0.94,
                "dx": 18,
                "dy": 18,
                "assigned_count": 279,
            },
            "rows": [
                {
                    "lau_id": "0180",
                    "municipality_name": "Stockholm",
                    "sorting_assignment": {
                        "label": "Separata kärl",
                        "classified_pixels": 12,
                        "confidence": 0.88,
                    },
                    "bag_assignment": {
                        "label": "Papper",
                        "classified_pixels": 10,
                        "confidence": 0.80,
                    },
                    "sorting_label": "Separata kärl",
                    "bin_configuration": "Four compartments bin",
                    "sorting_confidence": "0.880",
                    "sorting_pixels": "12",
                    "bag_label": "Papper",
                    "bag_material": "Collection Support Item: Plastic bags",
                    "bag_confidence": "0.800",
                    "bag_pixels": "10",
                    "collection_system": "Door to door",
                    "no_collection": "0",
                    "needs_manual_review": "0",
                    "review_reasons": "",
                }
            ],
        }
        with NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            raw_path = Path(handle.name)
        self.addCleanup(raw_path.unlink)

        details = load_raw_map_details(raw_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Four compartments bin",
                    "bag_material": "Collection Support Item: Plastic bags",
                }
            },
        )

    def test_load_reviewed_map_details_ignores_manual_review_rows(self):
        with NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(
                "lau_id,municipality_name,sorting_label,bin_configuration,sorting_confidence,sorting_pixels,bag_label,bag_material,bag_confidence,bag_pixels,collection_system,no_collection,needs_manual_review,review_reasons\n"
            )
            handle.write(
                "0180,Stockholm,Separata kärl,Separate bins,0.88,12,Papper,Collection Support Item: Paper bags,0.80,10,Door to door,0,0,\n"
            )
            handle.write(
                "0181,Södertälje,ET,,0.71,7,ET,,0.69,7,No separate collection,1,1,needs review\n"
            )
            csv_path = Path(handle.name)
        self.addCleanup(csv_path.unlink)

        details = load_reviewed_map_details(csv_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                }
            },
        )

    def test_load_raw_map_data_round_trips_json_artifact(self):
        raw_map_data = RawMapData(
            rows=[
                RawMapRow(
                    lau_id="0180",
                    municipality_name="Stockholm",
                    sorting_assignment=MapAssignment(
                        label="Separata kärl", classified_pixels=12, confidence=0.88
                    ),
                    bag_assignment=MapAssignment(
                        label="Papper", classified_pixels=10, confidence=0.80
                    ),
                    reviewed_fields={
                        "sorting_label": "Separata kärl",
                        "bin_configuration": "Separate bins",
                        "sorting_confidence": "0.880",
                        "sorting_pixels": "12",
                        "bag_label": "Papper",
                        "bag_material": "Collection Support Item: Paper bags",
                        "bag_confidence": "0.800",
                        "bag_pixels": "10",
                        "collection_system": "Door to door",
                        "no_collection": "0",
                        "needs_manual_review": "0",
                        "review_reasons": "",
                    },
                )
            ],
            left_transform=MapTransform(0.97, 0, 0, 283),
            right_transform=MapTransform(0.94, 18, 18, 279),
        )

        with NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            raw_path = Path(handle.name)
        self.addCleanup(raw_path.unlink)

        write_raw_map_data(raw_map_data, raw_path)

        loaded = load_raw_map_data(raw_path)

        self.assertEqual(loaded, raw_map_data)

    def test_load_raw_map_details_ignores_manual_review_rows(self):
        payload = {
            "format": "sweden-2024-map-raw",
            "version": 1,
            "left_transform": {
                "scale_multiplier": 0.97,
                "dx": 0,
                "dy": 0,
                "assigned_count": 283,
            },
            "right_transform": {
                "scale_multiplier": 0.94,
                "dx": 18,
                "dy": 18,
                "assigned_count": 279,
            },
            "rows": [
                {
                    "lau_id": "0180",
                    "municipality_name": "Stockholm",
                    "sorting_assignment": {
                        "label": "Separata kärl",
                        "classified_pixels": 12,
                        "confidence": 0.88,
                    },
                    "bag_assignment": {
                        "label": "Papper",
                        "classified_pixels": 10,
                        "confidence": 0.80,
                    },
                },
                {
                    "lau_id": "0580",
                    "municipality_name": "Linköping",
                    "sorting_assignment": {
                        "label": "Fyrfackskärl",
                        "classified_pixels": 22,
                        "confidence": 1.0,
                    },
                    "bag_assignment": {
                        "label": "ET",
                        "classified_pixels": 327,
                        "confidence": 0.706,
                    },
                },
            ],
        }
        with NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            raw_path = Path(handle.name)
        self.addCleanup(raw_path.unlink)

        details = load_raw_map_details(raw_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                }
            },
        )

    def test_load_map_details_dispatches_to_raw_json_loader(self):
        payload = {
            "format": "sweden-2024-map-raw",
            "version": 1,
            "left_transform": {
                "scale_multiplier": 0.97,
                "dx": 0,
                "dy": 0,
                "assigned_count": 283,
            },
            "right_transform": {
                "scale_multiplier": 0.94,
                "dx": 18,
                "dy": 18,
                "assigned_count": 279,
            },
            "rows": [
                {
                    "lau_id": "0180",
                    "municipality_name": "Stockholm",
                    "sorting_assignment": {
                        "label": "Separata kärl",
                        "classified_pixels": 12,
                        "confidence": 0.88,
                    },
                    "bag_assignment": {
                        "label": "Papper",
                        "classified_pixels": 10,
                        "confidence": 0.80,
                    },
                }
            ],
        }
        with NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            raw_path = Path(handle.name)
        self.addCleanup(raw_path.unlink)

        details = load_map_details(raw_path)

        self.assertEqual(
            details,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                }
            },
        )

    def test_apply_2024_map_details_updates_food_record_only(self):
        records = [
            {
                "nuts_or_lau_id": "0180",
                "waste_category": "Food waste",
                "collection_system": "Door to door",
                "bin_configuration": "",
                "allowed_materials": "",
                "property_values": [{"property_id": 1}],
            },
            {
                "nuts_or_lau_id": "0180",
                "waste_category": "Residual waste",
                "collection_system": "Door to door",
                "bin_configuration": "",
                "allowed_materials": "",
                "property_values": [{"property_id": 1}],
            },
        ]

        updated = _apply_2024_map_details(
            records,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": "Collection Support Item: Paper bags",
                }
            },
        )

        self.assertEqual(updated[0]["bin_configuration"], "Separate bins")
        self.assertEqual(
            updated[0]["allowed_materials"],
            "Collection Support Item: Paper bags",
        )
        self.assertEqual(updated[1]["waste_category"], "Residual waste")
        self.assertEqual(updated[1]["bin_configuration"], "")

    def test_apply_2024_map_details_turns_food_record_into_no_collection(self):
        records = [
            {
                "nuts_or_lau_id": "0180",
                "waste_category": "Food waste",
                "collection_system": "Door to door",
                "bin_configuration": "Separate bins",
                "allowed_materials": "Collection Support Item: Paper bags",
                "property_values": [{"property_id": 1}],
            }
        ]

        updated = _apply_2024_map_details(
            records,
            {
                "0180": {
                    "no_collection": True,
                    "bin_configuration": None,
                    "bag_material": None,
                }
            },
        )

        self.assertEqual(updated[0]["collection_system"], "No separate collection")
        self.assertEqual(updated[0]["bin_configuration"], "")
        self.assertEqual(updated[0]["allowed_materials"], "")
        self.assertEqual(updated[0]["property_values"], [])

    def test_apply_2024_map_details_adds_review_comment_for_manual_review_row(self):
        records = [
            {
                "nuts_or_lau_id": "0180",
                "waste_category": "Food waste",
                "collection_system": "Door to door",
                "bin_configuration": "Separate bins",
                "allowed_materials": "Collection Support Item: Paper bags",
                "property_values": [{"property_id": 1}],
            }
        ]

        updated = _apply_2024_map_details(
            records,
            {
                "0180": {
                    "no_collection": False,
                    "bin_configuration": "Separate bins",
                    "bag_material": None,
                    "needs_manual_review": True,
                    "review_reasons": ["bag material unresolved; bag map unclassified"],
                }
            },
        )

        self.assertEqual(updated[0]["bin_configuration"], "Separate bins")
        self.assertEqual(updated[0]["allowed_materials"], "")
        self.assertIn("review_comment", updated[0])
        self.assertIn(
            "bag material unresolved; bag map unclassified",
            updated[0]["review_comment"],
        )

    def test_write_raw_map_data(self):
        raw_map_data = RawMapData(
            rows=[
                RawMapRow(
                    lau_id="0180",
                    municipality_name="Stockholm",
                    sorting_assignment=MapAssignment(
                        label="Separata kärl", classified_pixels=12, confidence=0.88
                    ),
                    bag_assignment=MapAssignment(
                        label="Papper", classified_pixels=10, confidence=0.80
                    ),
                )
            ],
            left_transform=MapTransform(0.97, 0, 0, 283),
            right_transform=MapTransform(0.94, 18, 18, 279),
        )

        with NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            write_raw_map_data(raw_map_data, Path(handle.name))
            json_path = Path(handle.name)
        self.addCleanup(json_path.unlink)

        with open(json_path, encoding="utf-8") as handle:
            written_data = json.load(handle)

        self.assertEqual(
            written_data,
            {
                "format": "sweden-2024-map-raw",
                "version": 1,
                "left_transform": {
                    "scale_multiplier": 0.97,
                    "dx": 0,
                    "dy": 0,
                    "assigned_count": 283,
                },
                "right_transform": {
                    "scale_multiplier": 0.94,
                    "dx": 18,
                    "dy": 18,
                    "assigned_count": 279,
                },
                "rows": [
                    {
                        "lau_id": "0180",
                        "municipality_name": "Stockholm",
                        "sorting_assignment": {
                            "label": "Separata kärl",
                            "classified_pixels": 12,
                            "confidence": 0.88,
                        },
                        "bag_assignment": {
                            "label": "Papper",
                            "classified_pixels": 10,
                            "confidence": 0.80,
                        },
                        "sorting_label": "Separata kärl",
                        "bin_configuration": "Separate bins",
                        "sorting_confidence": "0.880",
                        "sorting_pixels": "12",
                        "bag_label": "Papper",
                        "bag_material": "Collection Support Item: Paper bags",
                        "bag_confidence": "0.800",
                        "bag_pixels": "10",
                        "collection_system": "Door to door",
                        "no_collection": "0",
                        "needs_manual_review": "0",
                        "review_reasons": "",
                    }
                ],
            },
        )


class PrepareSweden2024MapDataCommandTestCase(SimpleTestCase):
    @patch(
        "sources.waste_collection.management.commands.prepare_sweden_2024_map_data.extract_raw_map_data"
    )
    @patch(
        "sources.waste_collection.management.commands.prepare_sweden_2024_map_data.write_raw_map_data"
    )
    @patch(
        "sources.waste_collection.management.commands.prepare_sweden_2024_map_data.write_reviewed_map_rows"
    )
    def test_command_writes_raw_output_and_optional_review_csv(
        self, mock_write_review, mock_write_raw, mock_extract
    ):
        raw_map_data = RawMapData(
            rows=[
                RawMapRow(
                    lau_id="0180",
                    municipality_name="Stockholm",
                    sorting_assignment=MapAssignment(
                        label="Separata kärl", classified_pixels=25, confidence=0.84
                    ),
                    bag_assignment=MapAssignment(
                        label="Papper", classified_pixels=18, confidence=0.79
                    ),
                ),
                RawMapRow(
                    lau_id="0580",
                    municipality_name="Linköping",
                    sorting_assignment=MapAssignment(
                        label="Fyrfackskärl", classified_pixels=22, confidence=1.0
                    ),
                    bag_assignment=MapAssignment(
                        label="ET", classified_pixels=327, confidence=0.706
                    ),
                ),
            ],
            left_transform=MapTransform(0.97, 0, 0, 283),
            right_transform=MapTransform(0.94, 18, 18, 279),
        )
        mock_extract.return_value = raw_map_data

        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "source.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            output_path = Path(tmp_dir) / "raw.json"
            review_path = Path(tmp_dir) / "review.csv"
            stdout = StringIO()

            call_command(
                "prepare_sweden_2024_map_data",
                pdf=str(pdf_path),
                output=str(output_path),
                reviewed_output=str(review_path),
                stdout=stdout,
            )

        mock_extract.assert_called_once_with(pdf_path)
        mock_write_raw.assert_called_once_with(raw_map_data, output_path)
        mock_write_review.assert_called_once()

        output = stdout.getvalue()
        self.assertIn("Wrote raw map data for 2 municipalities", output)
        self.assertIn("Wrote editable reviewed CSV for 2 municipalities", output)
        self.assertIn("assigned=283", output)
        self.assertIn("assigned=279", output)
        self.assertIn("Rows flagged for manual review: 1", output)

    def test_command_fails_when_pdf_path_is_missing(self):
        with self.assertRaisesMessage(CommandError, "PDF file not found"):
            call_command(
                "prepare_sweden_2024_map_data",
                pdf="/tmp/does-not-exist.pdf",
                output="/tmp/out.json",
            )
