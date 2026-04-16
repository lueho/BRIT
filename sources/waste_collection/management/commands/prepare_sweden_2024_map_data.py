from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...sweden_2024_map_data import (
    build_prepared_rows,
    extract_raw_map_data,
    write_raw_map_data,
    write_reviewed_map_rows,
)


class Command(BaseCommand):
    help = (
        "Extract municipality-level Sweden 2024 food-waste system and bag-map "
        "classifications from page 24 of the Avfall Sverige PDF and export both "
        "a raw JSON provenance artifact and an editable reviewed CSV for import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pdf",
            required=True,
            help="Path to husha-llsavfall-i-siffror-2024.pdf",
        )
        parser.add_argument(
            "--output",
            required=True,
            help="Target JSON path for the raw municipality map data",
        )
        parser.add_argument(
            "--reviewed-output",
            "--review-output",
            dest="reviewed_output",
            default="",
            help="Optional CSV path for the editable reviewed municipality map data",
        )

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"])
        output_path = Path(options["output"])
        reviewed_output = (options.get("reviewed_output") or "").strip()
        if not pdf_path.exists():
            raise CommandError(f"PDF file not found: {pdf_path}")

        raw_map_data = extract_raw_map_data(pdf_path)
        write_raw_map_data(raw_map_data, output_path)
        prepared_rows = build_prepared_rows(raw_map_data)
        if reviewed_output:
            write_reviewed_map_rows(prepared_rows, Path(reviewed_output))

        manual_review_rows = sum(
            1 for row in prepared_rows if row["needs_manual_review"] == "1"
        )
        self.stdout.write(
            f"Wrote raw map data for {len(raw_map_data.rows)} municipalities to {output_path}"
        )
        if reviewed_output:
            self.stdout.write(
                "Wrote editable reviewed CSV for "
                f"{len(prepared_rows)} municipalities to {reviewed_output}"
            )
        self.stdout.write(
            "Left map transform: "
            f"scale={raw_map_data.left_transform.scale_multiplier:.2f}, "
            f"dx={raw_map_data.left_transform.dx}, dy={raw_map_data.left_transform.dy}, "
            f"assigned={raw_map_data.left_transform.assigned_count}"
        )
        self.stdout.write(
            "Right map transform: "
            f"scale={raw_map_data.right_transform.scale_multiplier:.2f}, "
            f"dx={raw_map_data.right_transform.dx}, dy={raw_map_data.right_transform.dy}, "
            f"assigned={raw_map_data.right_transform.assigned_count}"
        )
        self.stdout.write(f"Rows flagged for manual review: {manual_review_rows}")
