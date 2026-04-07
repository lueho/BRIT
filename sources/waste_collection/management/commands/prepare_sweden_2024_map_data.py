from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...sweden_2024_map_data import (
    build_prepared_rows,
    extract_raw_map_data,
    write_prepared_map_rows,
    write_raw_map_data,
)


class Command(BaseCommand):
    help = (
        "Extract municipality-level Sweden 2024 food-waste system and bag-map "
        "classifications from page 24 of the Avfall Sverige PDF and export a "
        "raw JSON artifact for later review or import."
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
            "--review-output",
            default="",
            help="Optional CSV path for a derived review sheet",
        )

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"])
        output_path = Path(options["output"])
        review_output = (options.get("review_output") or "").strip()
        if not pdf_path.exists():
            raise CommandError(f"PDF file not found: {pdf_path}")

        raw_map_data = extract_raw_map_data(pdf_path)
        write_raw_map_data(raw_map_data, output_path)
        prepared_rows = build_prepared_rows(raw_map_data)
        if review_output:
            write_prepared_map_rows(prepared_rows, Path(review_output))

        manual_review_rows = sum(
            1 for row in prepared_rows if row["needs_manual_review"] == "1"
        )
        self.stdout.write(
            f"Wrote raw map data for {len(raw_map_data.rows)} municipalities to {output_path}"
        )
        if review_output:
            self.stdout.write(
                f"Wrote derived review CSV for {len(prepared_rows)} municipalities to {review_output}"
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
