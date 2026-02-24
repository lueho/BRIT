#!/usr/bin/env python3
"""Standalone import script for BW 2024 waste collection data.

Reads the BW 2024 Excel file and calls the BRIT bulk import API.
No Django installation required — only openpyxl.

Usage::

    python import_bw_2024_standalone.py --api-url https://brit.example.com --token <TOKEN>
    python import_bw_2024_standalone.py --api-url http://localhost:8000 --username staff --password secret --dry-run
    python import_bw_2024_standalone.py --api-url http://localhost:8000 --token <TOKEN> --publication-status review
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

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

_CONN_RATE_COLS = [
    (20, 2019, None),
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

_PROP_SPECIFIC = 1
_PROP_TOTAL = 9
_PROP_CONN_RATE = 4
_UNIT_KG = "kg/(cap.*a)"
_UNIT_MG = "Mg/a"

_VALID_STATUSES = ("private", "review")
_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Row conversion helpers
# ---------------------------------------------------------------------------


def _resolve_date(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _collect_flyer_urls(row) -> list[str]:
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
    if value is None:
        return None
    if isinstance(value, int | float):
        return value
    return None


def _row_to_record(row) -> dict:
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
        "valid_from": _resolve_date(row[_COL["valid_from"]]),
        "valid_until": _resolve_date(row[_COL["valid_until"]])
        if row[_COL["valid_until"]]
        else None,
        "flyer_urls": _collect_flyer_urls(row),
        "property_values": _collect_property_values(row),
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def get_token(api_url: str, username: str, password: str) -> str:
    url = f"{api_url.rstrip('/')}/api-token-auth/"
    payload = json.dumps({"username": username, "password": password}).encode()
    req = Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        token = data.get("token")
        if not token:
            sys.exit(f"Token endpoint returned no token: {data}")
        return token
    except HTTPError as e:
        sys.exit(f"Token request failed ({e.code}): {e.read().decode()}")


def post_batch(
    api_url: str,
    token: str,
    records: list[dict],
    publication_status: str,
    dry_run: bool,
) -> dict:
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
        headers={"Content-Type": "application/json", "Authorization": f"Token {token}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        sys.exit(f"API request failed ({e.code}): {body}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Import BW 2024 waste collection data via the BRIT API."
    )
    parser.add_argument("--file", default=None, help="Path to the Excel file.")
    parser.add_argument(
        "--api-url",
        required=True,
        help="Base URL of the BRIT instance, e.g. https://brit.example.com",
    )
    parser.add_argument("--token", default=None, help="DRF auth token.")
    parser.add_argument("--username", default=None, help="Username (to obtain token).")
    parser.add_argument("--password", default=None, help="Password (to obtain token).")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without writing."
    )
    parser.add_argument(
        "--publication-status", default="private", choices=_VALID_STATUSES
    )
    parser.add_argument("--batch-size", type=int, default=_BATCH_SIZE)
    args = parser.parse_args()

    # Auth
    token = args.token
    if not token:
        if not args.username or not args.password:
            sys.exit("Provide --token or both --username and --password.")
        token = get_token(args.api_url, args.username, args.password)
        print("Token obtained.")

    # Excel
    file_path = (
        Path(args.file)
        if args.file
        else Path("BRIT_Deutschland_Baden-Württemberg_2024_SW.xlsx")
    )
    if not file_path.exists():
        sys.exit(f"Excel file not found: {file_path}")

    if args.dry_run:
        print("DRY RUN — no records will be written.")

    wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    raw_rows = list(wb.active.iter_rows(values_only=True))[1:]
    print(f"Read {len(raw_rows)} data rows from Excel.")

    all_records = [_row_to_record(r) for r in raw_rows]

    # Pre-filter records missing required fields; warn and skip them locally.
    records = []
    pre_skip_warnings = []
    for i, rec in enumerate(all_records, start=2):  # +2: 1-indexed + header row
        missing = []
        if not rec.get("collection_system"):
            missing.append("collection_system")
        if not rec.get("valid_from"):
            missing.append("valid_from")
        if missing:
            pre_skip_warnings.append(
                f"Row {i} ({rec.get('catchment_name') or rec.get('nuts_or_lau_id')}): "
                f"skipped — missing required field(s): {', '.join(missing)}"
            )
        else:
            records.append(rec)

    if pre_skip_warnings:
        print(f"Pre-flight: skipping {len(pre_skip_warnings)} invalid row(s).")

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
        records[i : i + args.batch_size]
        for i in range(0, len(records), args.batch_size)
    ]
    for idx, batch in enumerate(batches, start=1):
        print(
            f"  Posting batch {idx}/{len(batches)} ({len(batch)} records)…",
            end=" ",
            flush=True,
        )
        result = post_batch(
            args.api_url, token, batch, args.publication_status, args.dry_run
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
        print(f"created={stats.get('created', 0)} skipped={stats.get('skipped', 0)}")

    print("\n=== Import Summary ===")
    print(f"  Collections created:  {totals['created']}")
    print(f"  Collections skipped:  {totals['skipped']}")
    print(f"  Predecessor links:    {totals['predecessor_links']}")
    print(f"  CPVs created:         {totals['cpv_created']}")
    print(f"  CPVs skipped:         {totals['cpv_skipped']}")
    print(f"  Flyers created:       {totals['flyers_created']}")
    all_warnings = pre_skip_warnings + totals["warnings"]
    if all_warnings:
        print(f"\n  Warnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"    {w}")


if __name__ == "__main__":
    main()
