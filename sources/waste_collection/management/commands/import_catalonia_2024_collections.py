"""Management command to import Catalonia 2024 waste collection data.

Reads the Catalonia 2024 Excel file (BRIT_Katalonien_2024_SW.xlsx), converts
each row to the API payload format and POSTs to the
``/waste_collection/api/collection/import/`` endpoint.  Authentication uses a
DRF token that can be supplied directly or obtained by providing credentials.

This command is intended to be run **locally** (outside the container) against
a remote or local BRIT instance.  It does not import Django models directly.

Source file columns (0-based index):
  0  nuts3_name          NUTS-3 region name (Barcelona / Girona / Lleida / Tarragona)
  1  comarca             Comarca name
  2  codi                6-digit INE municipality code (province 2 + municipality 4 chars)
  3  municipi            Municipality name
  4  Collector           Collector name (often empty → municipality assumed)
  5  població_2020       Population 2020
  6  població_2024       Population 2024
  7  (formula)           Population ratio 2020/2024
  8  superfície          Area (km²)
  9  altitud             Altitude (m)
 10  Waste type          'Biowaste' or 'Residual waste'
 11  PaP_status_2020     Door-to-door status in 2020
 12  porta.a.porta_2024  Door-to-door status in 2024 (text description)
 13  Collection_system_2024  Canonical collection system label
 14  Access control/Use control_BP/PAP_2024  yes/no flags
 15  Connection rate to PaP_2020  %
 16  Connection rate to PaP_2024  %
 17  Collection frequency  BRIT frequency string
 18  Weekly access days_BP  (bring-point specific)
 19  Fee system           Fee system label
 20  Minimum bin size (L)
 21  Change implementation  Note about implementation change
 22  Change implementation year
 23  Quantity_2020_t      Total collected 2020 (tonnes)
 24  Quantity_2020_kg     Per-capita 2020 kg (formula)
 25  Quantity_2024_t      Total collected 2024 (tonnes)
 26  Quantity_2024_kg     Per-capita 2024 kg (formula, data_only=True gives result)
 27  Impurities_percentge_2020
 28  Impurities_percentage 2024
 29  Comments
 30  Sources              URLs and/or notes

LAU ID mapping
--------------
The Excel ``codi`` field stores the 6-character Spanish INE municipality code
(2-digit province + 4-digit sequential number, e.g. ``080018``).  The BRIT
database stores 5-character Eurostat LAU IDs (province 2 + sequential 3, e.g.
``08001``).  The conversion is: ``lau_id = codi[:5]``.

Collection system mapping
-------------------------
Excel value                         → BRIT canonical name
---------------------------------   ----------------------------------
PAP Total / PAP total               → Door to door
PAP Total + PxG                     → Door to door
PAP parcial                         → Door to door   (partial)
Propera implantació PAP             → Door to door   (planned — included)
Bring point                         → Bring point
No separate collection              → No separate collection
No PaP category / not shown as PaP → No separate collection
Recycling centre                    → Recycling centre
(residual waste rows, system=None)  → Door to door   (default)

Usage::

    python manage.py import_catalonia_2024_collections \\
        --api-url https://brit.example.com --token <TOKEN>
    python manage.py import_catalonia_2024_collections \\
        --api-url http://localhost:8000 --username staff --password secret
    python manage.py import_catalonia_2024_collections \\
        --api-url http://localhost:8000 --token <TOKEN> --dry-run
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import openpyxl
from django.core.management.base import BaseCommand, CommandError

# ---------------------------------------------------------------------------
# Default paths / constants
# ---------------------------------------------------------------------------

_DEFAULT_EXCEL = Path("BRIT_Katalonien_2024_SW.xlsx")
_BATCH_SIZE = 50
_VALID_STATUSES = ("private", "review")

# ---------------------------------------------------------------------------
# Source metadata
# ---------------------------------------------------------------------------

# Primary dataset source (placeholder — update with the real publication URL)
_SOURCE_URL = (
    "https://www.arc.cat/ca/publicacions/pdf/residus-municipals/"
    "estadistiques-de-residus-municipals-de-catalunya-2024.pdf"
)

# ---------------------------------------------------------------------------
# Property IDs (verified against live DB)
# ---------------------------------------------------------------------------
_PROP_SPECIFIC = 1  # "specific waste collected"  [kg/(cap.*a)]
_PROP_TOTAL = 9  # "total waste collected"      [Mg/a]
_PROP_CONN_RATE = 4  # "Connection rate"            [% of households]

_UNIT_KG = "kg/(cap.*a)"
_UNIT_MG = "Mg/a"
_UNIT_PCT_HH = "% of households"

# ---------------------------------------------------------------------------
# Data year represented by this file
# ---------------------------------------------------------------------------
_DATA_YEAR = 2024
_VALID_FROM = date(_DATA_YEAR, 1, 1)
_VALID_UNTIL = date(_DATA_YEAR, 12, 31)

# ---------------------------------------------------------------------------
# BRIT canonical names
# ---------------------------------------------------------------------------
_CS_DOOR_TO_DOOR = "Door to door"
_CS_BRING_POINT = "Bring point"
_CS_NO_SEPARATE = "No separate collection"
_CS_RECYCLING_CENTRE = "Recycling centre"

_WC_BIOWASTE = "Biowaste"
_WC_RESIDUAL = "Residual waste"

# ---------------------------------------------------------------------------
# Collection system mapping: Excel label → BRIT name
# ---------------------------------------------------------------------------
_COLLECTION_SYSTEM_MAP: dict[str, str] = {
    "pap total": _CS_DOOR_TO_DOOR,
    "pap total + pxg": _CS_DOOR_TO_DOOR,
    "pap parcial": _CS_DOOR_TO_DOOR,
    "propera implantació pap": _CS_DOOR_TO_DOOR,
    "bring point": _CS_BRING_POINT,
    "no separate collection": _CS_NO_SEPARATE,
    "no pap category / not shown as pap": _CS_NO_SEPARATE,
    "recycling centre": _CS_RECYCLING_CENTRE,
}

# ---------------------------------------------------------------------------
# Fee system mapping: Excel label → BRIT FeeSystem name
# ---------------------------------------------------------------------------
_FEE_SYSTEM_MAP: dict[str, str] = {
    "pay as you throw (payt)": "Pay as you throw (PAYT)",
    "payt": "Pay as you throw (PAYT)",
    "pxg": "Pay as you throw (PAYT)",  # "pagament per generació" = PAYT
    "basic fee": "Flat fee",
    "no payt": "Flat fee",
}

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
_BROKEN_WEBARCHIVE_RE = re.compile(
    r"(https?://web\.archive\.org/web/\d{6}),\s*(\d{6,}/https?://)",
    re.IGNORECASE,
)
_URL_START_RE = re.compile(r"https?://", re.IGNORECASE)


def _split_source_cell(raw) -> tuple[list[str], list[str]]:
    """Split a source cell into (urls, notes)."""
    text = " ".join(str(raw or "").split())
    if not text:
        return [], []
    text = _BROKEN_WEBARCHIVE_RE.sub(r"\1\2", text)
    if _URL_START_RE.search(text) is None:
        return [], [text]
    urls: list[str] = []
    notes: list[str] = []
    for part in text.split(", "):
        part = part.strip(" ,;")
        if not part:
            continue
        if part.lower().startswith("http"):
            urls.append(part)
        else:
            notes.append(part)
    return urls, notes


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


# ---------------------------------------------------------------------------
# Row-level helpers
# ---------------------------------------------------------------------------


def _ine_to_lau(codi: str | None) -> str:
    """Convert a 6-character INE code to a 5-character Eurostat LAU ID.

    The INE code format is: 2-digit province + 4-digit sequential number
    (e.g. ``080018``).  The BRIT Eurostat LAU ID uses the same two fields but
    drops the last digit of the INE sequential part (e.g. ``08001``).
    """
    if not codi or len(codi) < 5:
        return ""
    return codi[:5]


def _map_collection_system(raw: str | None, waste_type: str) -> str:
    """Return the BRIT collection system name for a raw Excel value.

    For residual waste rows the ``Collection_system_2024`` cell is often empty;
    those rows default to *Door to door* because the municipality always
    collects residual waste in some way.
    """
    if raw:
        key = raw.strip().lower()
        mapped = _COLLECTION_SYSTEM_MAP.get(key)
        if mapped:
            return mapped
    if waste_type == _WC_RESIDUAL:
        return _CS_DOOR_TO_DOOR
    return ""


def _map_fee_system(raw: str | None) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    return _FEE_SYSTEM_MAP.get(key, "")


def _to_float_or_none(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", ".").strip())
    except (ValueError, AttributeError):
        return None


def _date_to_str(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------


def _row_to_record(row: tuple) -> dict | None:
    """Convert one Excel row to an importer-compatible record dict.

    Returns ``None`` for rows that should be skipped entirely (header
    fragments, empty rows, waste types outside scope).
    """
    waste_type = row[10]
    if waste_type not in (_WC_BIOWASTE, _WC_RESIDUAL):
        return None

    codi = str(row[2] or "").strip()
    lau_id = _ine_to_lau(codi)
    if not lau_id:
        return None

    collection_system_raw = row[13]
    collection_system = _map_collection_system(collection_system_raw, waste_type)

    # Build source URLs: use row-level Sources cell + fallback to dataset URL
    raw_sources = row[30]
    row_urls, row_notes = _split_source_cell(raw_sources)
    flyer_urls = _dedupe_preserve_order(row_urls or [_SOURCE_URL])

    # Property values
    pvs: list[dict] = []

    # 2024 per-capita specific quantity [kg/(cap.*a)]
    qty_kg_per_cap = _to_float_or_none(row[26])
    if qty_kg_per_cap is not None and qty_kg_per_cap > 0:
        pvs.append(
            {
                "property_id": _PROP_SPECIFIC,
                "unit_name": _UNIT_KG,
                "year": _DATA_YEAR,
                "average": round(qty_kg_per_cap, 4),
                "flyer_urls": flyer_urls,
            }
        )

    # 2024 total quantity [Mg/a]
    qty_2024_t = _to_float_or_none(row[25])
    if qty_2024_t is not None and qty_2024_t > 0:
        pvs.append(
            {
                "property_id": _PROP_TOTAL,
                "unit_name": _UNIT_MG,
                "year": _DATA_YEAR,
                "average": round(qty_2024_t, 4),
                "flyer_urls": flyer_urls,
            }
        )

    # 2020 per-capita specific quantity [kg/(cap.*a)]
    qty_2020_kg_per_cap = _to_float_or_none(row[24])
    if qty_2020_kg_per_cap is not None and qty_2020_kg_per_cap > 0:
        pvs.append(
            {
                "property_id": _PROP_SPECIFIC,
                "unit_name": _UNIT_KG,
                "year": 2020,
                "average": round(qty_2020_kg_per_cap, 4),
                "flyer_urls": flyer_urls,
            }
        )

    # 2020 total quantity [Mg/a]
    qty_2020_t = _to_float_or_none(row[23])
    if qty_2020_t is not None and qty_2020_t > 0:
        pvs.append(
            {
                "property_id": _PROP_TOTAL,
                "unit_name": _UNIT_MG,
                "year": 2020,
                "average": round(qty_2020_t, 4),
                "flyer_urls": flyer_urls,
            }
        )

    # Connection rate to PAP 2024 [% of households] — biowaste only
    if waste_type == _WC_BIOWASTE:
        conn_rate_raw = row[16]
        conn_rate = _to_float_or_none(conn_rate_raw)
        if conn_rate is not None:
            pvs.append(
                {
                    "property_id": _PROP_CONN_RATE,
                    "unit_name": _UNIT_PCT_HH,
                    "year": _DATA_YEAR,
                    "average": round(conn_rate, 4),
                    "flyer_urls": flyer_urls,
                }
            )

    # Description: combine comments + implementation notes
    description_parts: list[str] = []
    comments = str(row[29] or "").strip()
    if comments:
        description_parts.append(comments)
    change_impl = str(row[21] or "").strip()
    change_year = row[22]
    if change_impl and change_year:
        description_parts.append(
            f"Implementation change: {change_impl} ({int(change_year)})"
        )
    elif change_impl:
        description_parts.append(f"Implementation change: {change_impl}")

    return {
        "nuts_or_lau_id": lau_id,
        "catchment_name": "",
        "collector_name": str(row[4] or "").strip(),
        "collection_system": collection_system,
        "waste_category": waste_type,
        "allowed_materials": "",
        "forbidden_materials": "",
        "fee_system": _map_fee_system(row[19]),
        "frequency": str(row[17] or "").strip(),
        "connection_type": "",
        "min_bin_size": _to_float_or_none(row[20]),
        "required_bin_capacity": None,
        "required_bin_capacity_reference": "",
        "description": "\n\n".join(description_parts),
        "valid_from": _date_to_str(_VALID_FROM),
        "valid_until": _date_to_str(_VALID_UNTIL),
        "sources": row_notes,
        "flyer_urls": flyer_urls,
        "property_values": pvs,
    }


# ---------------------------------------------------------------------------
# Workbook loader
# ---------------------------------------------------------------------------


def _load_records(file_path: Path) -> tuple[list[dict], list[str], int]:
    """Load the Catalonia workbook into importer-compatible records.

    Returns:
        Tuple of (valid_records, preflight_warnings, total_data_row_count).
    """
    workbook = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    next(rows, None)  # skip header

    records: list[dict] = []
    warnings: list[str] = []
    row_count = 0

    for row_number, row in enumerate(rows, start=2):
        row_count += 1

        waste_type = row[10]
        if waste_type not in (_WC_BIOWASTE, _WC_RESIDUAL):
            continue

        record = _row_to_record(row)
        if record is None:
            warnings.append(
                f"Row {row_number}: skipped — missing LAU code "
                f"(codi={row[2]!r}, municipi={row[3]!r})"
            )
            continue

        missing = []
        if not record.get("collection_system"):
            missing.append("collection_system")
        if missing:
            warnings.append(
                f"Row {row_number} ({row[3]!r}, {waste_type!r}): "
                f"skipped — missing required field(s): {', '.join(missing)}; "
                f"raw collection_system={row[13]!r}"
            )
            continue

        record["_excel_row"] = row_number
        records.append(record)

    return records, warnings, row_count


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def _merge_unresolved_frequencies(target: dict, source: dict) -> None:
    for frequency_name, details in (source or {}).items():
        reason = details.get("reason", "not_found")
        count = int(details.get("count", 0))
        existing = target.setdefault(
            frequency_name,
            {"count": 0, "reason": reason},
        )
        existing["count"] = int(existing.get("count", 0)) + count
        if existing.get("reason") != reason:
            existing["reason"] = "mixed"


class Command(BaseCommand):
    """Import Catalonia 2024 waste collection data via the BRIT API."""

    help = "Import Catalonia 2024 waste collection data via the BRIT API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help=(f"Path to the Excel file (default: {_DEFAULT_EXCEL})."),
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
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_token(self, api_url: str, username: str, password: str) -> str:
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
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Could not obtain token: {exc}") from exc

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _post_batch(
        self,
        api_url: str,
        token: str,
        records: list[dict],
        publication_status: str,
        dry_run: bool,
    ) -> dict:
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
        except CommandError:
            raise
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

        # Auth
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
            file_path = _DEFAULT_EXCEL
        else:
            file_path = Path(file_path)

        if not file_path.exists():
            raise CommandError(f"Excel file not found: {file_path}")

        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")

        records, pre_skip_warnings, row_count = _load_records(file_path)
        self.stdout.write(f"Read {row_count} data rows from Excel.\n")
        self.stdout.write(
            f"Loaded {len(records)} importable records "
            f"(skipped {len(pre_skip_warnings)} in pre-flight).\n"
        )

        totals = {
            "created": 0,
            "unchanged": 0,
            "skipped": 0,
            "predecessor_links": 0,
            "cpv_created": 0,
            "cpv_unchanged": 0,
            "cpv_skipped": 0,
            "flyers_created": 0,
            "sources_created": 0,
            "review_comments_created": 0,
            "warnings": [],
            "unresolved_frequencies": {},
        }
        totals["skipped"] += len(pre_skip_warnings)

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
                "unchanged",
                "skipped",
                "predecessor_links",
                "cpv_created",
                "cpv_unchanged",
                "cpv_skipped",
                "flyers_created",
                "sources_created",
                "review_comments_created",
            ):
                totals[key] += stats.get(key, 0)
            totals["warnings"].extend(stats.get("warnings", []))
            _merge_unresolved_frequencies(
                totals["unresolved_frequencies"],
                stats.get("unresolved_frequencies", {}),
            )
            self.stdout.write(
                f" created={stats.get('created', 0)}"
                f" unchanged={stats.get('unchanged', 0)}"
                f" skipped={stats.get('skipped', 0)}\n"
            )

        self.stdout.write("\n=== Import Summary ===\n")
        self.stdout.write(f"  Collections created:   {totals['created']}\n")
        self.stdout.write(f"  Collections unchanged: {totals['unchanged']}\n")
        self.stdout.write(f"  Collections skipped:   {totals['skipped']}\n")
        self.stdout.write(f"  Predecessor links:     {totals['predecessor_links']}\n")
        self.stdout.write(f"  CPVs created:          {totals['cpv_created']}\n")
        self.stdout.write(f"  CPVs unchanged:        {totals['cpv_unchanged']}\n")
        self.stdout.write(f"  CPVs skipped:          {totals['cpv_skipped']}\n")
        self.stdout.write(f"  Flyers created:        {totals['flyers_created']}\n")
        self.stdout.write(f"  Sources created:       {totals['sources_created']}\n")

        all_warnings = pre_skip_warnings + totals["warnings"]
        if all_warnings:
            self.stdout.write(f"\n  Warnings ({len(all_warnings)}):\n")
            for w in all_warnings:
                self.stdout.write(f"    {w}\n")

        if totals["unresolved_frequencies"]:
            self.stdout.write(
                "\n  Unresolved frequencies (manual fix needed after import):\n"
            )
            unresolved_items = sorted(
                totals["unresolved_frequencies"].items(),
                key=lambda item: (-int(item[1].get("count", 0)), item[0]),
            )
            for frequency_name, details in unresolved_items:
                self.stdout.write(
                    f"    {frequency_name} "
                    f"(count={details.get('count', 0)}, "
                    f"reason={details.get('reason', 'not_found')})\n"
                )
