"""Management command to import Baden-Württemberg 2024 waste collection data.

Reads the BW 2024 Excel file, converts each row to the API payload format and
POSTs to the ``/api/collections/import/`` endpoint.  Authentication uses a
DRF token that can be supplied directly or obtained by providing credentials.

This command is intended to be run **locally** (outside the container) against
a remote or local BRIT instance.  It does not import Django models directly.

Usage::

    python manage.py import_bw_2024_collections --api-url https://example.com --token <TOKEN>
    python manage.py import_bw_2024_collections --api-url http://localhost:8000 --username staff --password secret
    python manage.py import_bw_2024_collections --api-url http://localhost:8000 --token <TOKEN> --dry-run
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import openpyxl
from django.core.management.base import BaseCommand, CommandError

# ---------------------------------------------------------------------------
# Column indices (0-based) in the BW 2024 Excel sheet
# ---------------------------------------------------------------------------
_COL = {
    "catchment_name": 0,
    "nuts_or_lau_id": 2,
    "collector": 3,
    "collection_system": 4,
    "waste_category": 6,
    "connection_type": 10,
    "allowed_materials": 11,
    "forbidden_materials": 12,
    "fee_system": 13,
    "frequency": 14,
    "min_bin_size": 15,
    "required_bin_capacity": 16,
    "required_bin_capacity_reference": 17,
    "conn_rate_basis": 26,
    "description": 37,
    "sources": 38,
    "sources_new": 39,
    "valid_from": 40,
    "valid_until": 41,
}

# (column_index, year, unit_name)
_CONN_RATE_COLS = [
    (20, 2019, None),  # unit resolved from basis
    (21, 2020, None),
    (22, 2021, None),
    (23, 2022, None),
    (24, 2023, None),
    (25, 2024, None),
]

_SPECIFIC_KG_COLS = [
    (27, 2015),
    (28, 2016),
    (29, 2017),
    (30, 2018),
    (31, 2019),
    (32, 2020),
    (33, 2021),
]

# The BW sheet labels these as "Specific ... [t/year]", but the values are
# total annual amounts and must map to "total waste collected" (Mg/a).
_TOTAL_MG_COLS = [
    (34, 2022),
    (35, 2023),
    (36, 2024),
]

_BASIS_TO_UNIT = {
    "bin ratio": "% of residual waste bins",
    "households": "% of households",
    "household": "% of households",
    "properties": "% of residential properties",
}
_CONN_RATE_FALLBACK_UNIT = "% (of unknown reference)"

# Property IDs (verified against live DB)
_PROP_SPECIFIC = 1  # specific waste collected
_PROP_TOTAL = 9  # total waste collected
_PROP_CONN_RATE = 4  # Connection rate

_UNIT_KG = "kg/(cap.*a)"
_UNIT_MG = "Mg/a"

_VALID_STATUSES = ("private", "review")

_BATCH_SIZE = 50  # records per POST request


def _resolve_date(value):
    """Convert an openpyxl cell value to a Python date, or None."""

    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _collect_flyer_urls(row) -> list[str]:
    """Extract HTTP URLs from the sources columns (38, 39)."""
    urls = []
    for col in (_COL["sources"], _COL["sources_new"]):
        raw = row[col]
        if not raw:
            continue
        for part in str(raw).split(","):
            part = part.strip()
            if part.startswith("http"):
                urls.append(part)
    return urls


def _collect_property_values(row) -> list[dict]:
    """Build property-value dicts from connection-rate and specific-waste columns."""
    pvs = []

    basis_raw = row[_COL["conn_rate_basis"]]
    conn_rate_unit_name = _CONN_RATE_FALLBACK_UNIT
    if basis_raw:
        mapped = _BASIS_TO_UNIT.get(str(basis_raw).lower().strip())
        if mapped:
            conn_rate_unit_name = mapped

    for col, year, _ in _CONN_RATE_COLS:
        value = row[col]
        if value is not None:
            pvs.append(
                {
                    "property_id": _PROP_CONN_RATE,
                    "unit_name": conn_rate_unit_name,
                    "year": year,
                    "average": float(value),
                }
            )

    for col, year in _SPECIFIC_KG_COLS:
        value = row[col]
        if value is not None:
            pvs.append(
                {
                    "property_id": _PROP_SPECIFIC,
                    "unit_name": _UNIT_KG,
                    "year": year,
                    "average": float(value),
                }
            )

    for col, year in _TOTAL_MG_COLS:
        value = row[col]
        if value is not None:
            pvs.append(
                {
                    "property_id": _PROP_TOTAL,
                    "unit_name": _UNIT_MG,
                    "year": year,
                    "average": float(value),
                }
            )

    return pvs


def _to_decimal_or_none(value):
    """Return value if numeric, otherwise None."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return value
    return None


def _row_to_record(row) -> dict:
    """Convert a raw Excel row tuple into a CollectionImporter-compatible dict."""
    valid_from = _resolve_date(row[_COL["valid_from"]])
    valid_until_raw = row[_COL["valid_until"]]
    valid_until = _resolve_date(valid_until_raw) if valid_until_raw else None

    return {
        "nuts_or_lau_id": row[_COL["nuts_or_lau_id"]] or "",
        "catchment_name": row[_COL["catchment_name"]] or "",
        "collector_name": row[_COL["collector"]] or "",
        "collection_system": row[_COL["collection_system"]] or "",
        "waste_category": row[_COL["waste_category"]] or "",
        "allowed_materials": row[_COL["allowed_materials"]] or "",
        "forbidden_materials": row[_COL["forbidden_materials"]] or "",
        "fee_system": row[_COL["fee_system"]] or "",
        "frequency": row[_COL["frequency"]] or "",
        "connection_type": row[_COL["connection_type"]] or "",
        "min_bin_size": _to_decimal_or_none(row[_COL["min_bin_size"]]),
        "required_bin_capacity": _to_decimal_or_none(
            row[_COL["required_bin_capacity"]]
        ),
        "required_bin_capacity_reference": row[_COL["required_bin_capacity_reference"]]
        or "",
        "description": row[_COL["description"]] or "",
        "valid_from": valid_from,
        "valid_until": valid_until,
        "flyer_urls": _collect_flyer_urls(row),
        "property_values": _collect_property_values(row),
    }


def _date_to_str(value) -> str | None:
    """Serialise a date to ISO 8601 string for the JSON payload."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _records_to_json_serialisable(records: list[dict]) -> list[dict]:
    """Convert Python date objects in records to ISO strings."""
    out = []
    for rec in records:
        r = dict(rec)
        r["valid_from"] = _date_to_str(r.get("valid_from"))
        r["valid_until"] = _date_to_str(r.get("valid_until"))
        out.append(r)
    return out


class Command(BaseCommand):
    """Import BW 2024 waste collection data by calling the BRIT API."""

    help = "Import Baden-Württemberg 2024 waste collection data via the BRIT API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to the Excel file (default: BRIT_Deutschland_Baden-Württemberg_2024_SW.xlsx).",
        )
        parser.add_argument(
            "--api-url",
            type=str,
            required=True,
            help="Base URL of the BRIT instance, e.g. https://brit.example.com",
        )
        parser.add_argument(
            "--token",
            type=str,
            default=None,
            help="DRF auth token. Omit to obtain one via --username/--password.",
        )
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Username to obtain a DRF token (requires --password).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Password to obtain a DRF token (requires --username).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pass dry_run=true to the API — no records are written.",
        )
        parser.add_argument(
            "--publication-status",
            type=str,
            default="private",
            choices=_VALID_STATUSES,
            help="Publication status for created records (default: private).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_BATCH_SIZE,
            help=f"Number of records per API request (default: {_BATCH_SIZE}).",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_token(self, api_url: str, username: str, password: str) -> str:
        """Obtain a DRF token via the token-auth endpoint."""
        try:
            url = f"{api_url.rstrip('/')}/api/auth/token/"
            payload = json.dumps({"username": username, "password": password}).encode()
            req = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            token = data.get("token")
            if not token:
                raise CommandError(f"Token endpoint returned no token: {data}")
            return token
        except Exception as exc:
            raise CommandError(f"Could not obtain token: {exc}") from exc

    def _post_batch(
        self,
        api_url: str,
        token: str,
        records: list[dict],
        publication_status: str,
        dry_run: bool,
    ) -> dict:
        """POST one batch of records to the import endpoint; return stats dict."""
        try:
            url = f"{api_url.rstrip('/')}/waste_collection/api/collection/import/"
            payload = json.dumps(
                {
                    "records": records,
                    "publication_status": publication_status,
                    "dry_run": dry_run,
                }
            ).encode()
            req = Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Token {token}",
                },
                method="POST",
            )
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            raise CommandError(f"API request failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        api_url = options["api_url"]
        dry_run = options["dry_run"]
        publication_status = options["publication_status"]
        batch_size = options["batch_size"]
        file_path = options["file"]

        # Resolve auth token
        token = options.get("token")
        if not token:
            username = options.get("username")
            password = options.get("password")
            if not username or not password:
                raise CommandError("Provide --token or both --username and --password.")
            token = self._get_token(api_url, username, password)
            self.stdout.write("Token obtained.\n")

        # Resolve Excel path
        if file_path is None:
            file_path = Path("BRIT_Deutschland_Baden-Württemberg_2024_SW.xlsx")
        else:
            file_path = Path(file_path)

        if not file_path.exists():
            raise CommandError(f"Excel file not found: {file_path}")

        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")

        wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
        raw_rows = list(wb.active.iter_rows(values_only=True))[1:]
        self.stdout.write(f"Read {len(raw_rows)} data rows from Excel.\n")

        records = _records_to_json_serialisable([_row_to_record(r) for r in raw_rows])

        # Aggregate stats across batches
        totals = {
            "created": 0,
            "skipped": 0,
            "predecessor_links": 0,
            "cpv_created": 0,
            "cpv_skipped": 0,
            "flyers_created": 0,
            "warnings": [],
        }

        batches = [
            records[i : i + batch_size] for i in range(0, len(records), batch_size)
        ]
        for idx, batch in enumerate(batches, start=1):
            self.stdout.write(
                f"  Posting batch {idx}/{len(batches)} ({len(batch)} records)…"
            )
            sys.stdout.flush()
            result = self._post_batch(
                api_url, token, batch, publication_status, dry_run
            )
            stats = result.get("stats", {})
            for key in (
                "created",
                "skipped",
                "predecessor_links",
                "cpv_created",
                "cpv_skipped",
                "flyers_created",
            ):
                totals[key] += stats.get(key, 0)
            totals["warnings"].extend(stats.get("warnings", []))
            self.stdout.write(
                f" created={stats.get('created', 0)} skipped={stats.get('skipped', 0)}\n"
            )

        self.stdout.write("\n=== Import Summary ===\n")
        self.stdout.write(f"  Collections created:  {totals['created']}\n")
        self.stdout.write(f"  Collections skipped:  {totals['skipped']}\n")
        self.stdout.write(f"  Predecessor links:    {totals['predecessor_links']}\n")
        self.stdout.write(f"  CPVs created:         {totals['cpv_created']}\n")
        self.stdout.write(f"  CPVs skipped:         {totals['cpv_skipped']}\n")
        self.stdout.write(f"  Flyers created:       {totals['flyers_created']}\n")
        if totals["warnings"]:
            self.stdout.write(f"\n  Warnings ({len(totals['warnings'])}):\n")
            for w in totals["warnings"]:
                self.stdout.write(f"    {w}\n")
