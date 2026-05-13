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
 14  Access control/Use control_BP/PAP_2024  yes/no flags (BP first, PAP second when slash-separated)
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
Propera implantació PAP             → skipped        (planned, not active in 2024)
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
_COUNTRY_CODE = "ES"

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
    "bring point": _CS_BRING_POINT,
    "no separate collection": _CS_NO_SEPARATE,
    "no pap category / not shown as pap": _CS_NO_SEPARATE,
    "recycling centre": _CS_RECYCLING_CENTRE,
}

# ---------------------------------------------------------------------------
# Collection frequency normalisation: Excel string → BRIT CollectionFrequency name
#
# Maps each human-readable Excel frequency string to its canonical DB name,
# which is auto-generated by CollectionFrequencyScheduleService.canonical_name()
# from the per-season structure stored in CollectionCountOptions.
#
# Format of canonical names: "Fixed-Seasonal; <Season1> <count> per year; <Season2> <count> per year"
# where each count is the number of collections *within that season*.
#
# Per-season counts are computed from the stated weekly cadence × average weeks in the season
# (using 365/12 days per month), then adjusted where necessary so the sum matches the
# annual total stated in the source spreadsheet.
# ---------------------------------------------------------------------------
_FREQUENCY_NORMALISE_MAP: dict[str, str] = {
    # Spreadsheet: "xx per year (2/wk Oct–Apr, 3/wk May–Sep)"
    # Oct–Apr: round(2 × 30.32 wks) = 61; May–Sep: round(3 × 21.86 wks) = 66; total = 127
    "Fixed-Seasonal; xx per year (2 per week from October - April, 3 per week from May - September)": (
        "Fixed-Seasonal; October-April 61 per year; May-September 66 per year"
    ),
    # Spreadsheet: "205 per year (3/wk Oct–Jun, 7/wk Jul–Sep)"
    # Oct–Jun: round(3 × 39.04 wks) = 117; Jul–Sep: 205 − 117 = 88; total = 205
    "Fixed-Seasonal; 205 per year (3 per week from October - June and 7 per week from July - September)": (
        "Fixed-Seasonal; October-June 117 per year; July-September 88 per year"
    ),
    # Spreadsheet: "165 per year (3/wk Sep–Jun, 4/wk Jul–Aug)"
    # Sep–Jun: round(3 × 43.32 wks) = 130; Jul–Aug: 165 − 130 = 35; total = 165
    "Fixed-Seasonal; 165 per year (3 per week from September - June, 4 per week from July - August)": (
        "Fixed-Seasonal; September-June 130 per year; July-August 35 per year"
    ),
    # Spreadsheet: "169 per year (3/wk mid-Sep–mid-Jun, 4/wk mid-Jun–mid-Sep)"
    # Model uses whole months: Sep–Jun (9 mo) and Jun–Sep (4 mo).
    # Sep–Jun: round(3 × 43.32 wks) = 130; Jun–Sep: 169 − 130 = 39; total = 169
    "Fixed-Seasonal; 169 per year (3 per week from mid September - mid June & 4 per week from mid June - mid September)": (
        "Fixed-Seasonal; September-June 130 per year; June-September 39 per year"
    ),
}

# ---------------------------------------------------------------------------
# Access control mapping: Excel col 14 → (bool | None, bool | None)
#
# Column 14 is "Access control/Use control_BP/PAP_2024".
# The slash separates BP (bring-point) and PAP (door-to-door) values:
#   - Single 'yes'/'no'  → applies to whichever system the row uses
#   - 'BP_value/PAP_value' (e.g. 'yes/no') → first token = BP, second = PAP
#
# Returns a (access_control_bp, access_control_pap) tuple.
# None means the field is not specified for that component.
# ---------------------------------------------------------------------------


def _parse_yes_no(token: str) -> bool | None:
    """Map a single 'yes'/'no' token (case-insensitive) to bool or None."""
    t = token.strip().lower()
    if t == "yes":
        return True
    if t == "no":
        return False
    return None


def _map_access_control(raw) -> tuple[bool | None, bool | None]:
    """Return (access_control_bp, access_control_pap) from col 14 raw value.

    Slash-separated values encode BP/PAP independently (first token = BP,
    second token = PAP).  A single token applies to whichever component is
    relevant for that row's collection system; the other component is left None.
    """
    if raw is None:
        return None, None
    parts = [p.strip() for p in str(raw).strip().split("/")]
    if len(parts) == 2:
        # Explicit BP/PAP pair (PAP parcial rows)
        return _parse_yes_no(parts[0]), _parse_yes_no(parts[1])
    # Single value — caller decides which field to assign; return in BP slot
    # for bring-point rows and PAP slot for door-to-door rows.
    # The _row_to_record function routes to the correct field.
    return _parse_yes_no(parts[0]), None


def _access_control_fields(
    raw, collection_system: str | None
) -> dict[str, bool | None]:
    """Return {'access_control_bp': ..., 'access_control_pap': ...} for a row.

    Slash-separated values (PAP parcial rows) directly supply both components.
    Single values are routed to the field that matches the collection system:
    - Bring point rows  → access_control_bp
    - Door-to-door rows → access_control_pap
    - Others            → both None
    """
    ac_bp, ac_pap = _map_access_control(raw)
    if raw is not None and "/" not in str(raw):
        # Single token — route to the correct component field
        if collection_system == _CS_BRING_POINT:
            ac_bp, ac_pap = ac_bp, None
        elif collection_system == _CS_DOOR_TO_DOOR:
            ac_bp, ac_pap = None, ac_bp
        else:
            ac_bp, ac_pap = None, None
    return {"access_control_bp": ac_bp, "access_control_pap": ac_pap}


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
# Partial scheme patterns that arise from copy-paste corruption (e.g. "ttps://…").
_PARTIAL_SCHEME_RE = re.compile(r"t{1,2}ps?://", re.IGNORECASE)


def _split_source_cell(raw) -> tuple[list[str], list[str]]:
    """Split a source cell into (urls, notes).

    Handles comma-separated entries as well as space-separated URL pairs that
    occasionally appear in the source data (e.g. ``url1 url2`` without a
    comma delimiter).  Also repairs truncated schemes such as ``ttps://``
    (missing leading ``h``) to avoid storing them as plain text notes, which
    would crash when the importer tries to write them into a 50-char DB column.
    """
    text = " ".join(str(raw or "").split())
    if not text:
        return [], []
    text = _BROKEN_WEBARCHIVE_RE.sub(r"\1\2", text)
    if _URL_START_RE.search(text) is None and not _PARTIAL_SCHEME_RE.search(text):
        return [], [text]
    urls: list[str] = []
    notes: list[str] = []
    for part in text.split(", "):
        part = part.strip(" ,;")
        if not part:
            continue
        if part.lower().startswith("http"):
            # A single comma-separated token can itself contain two URLs joined
            # by a space (no comma).  Re-split on embedded "http" boundaries,
            # but only on boundaries preceded by a space (not inside
            # web.archive.org paths which embed the original URL in the path).
            scheme_matches = list(re.finditer(r"(?<=\s)https?://", part, re.IGNORECASE))
            if not scheme_matches:
                urls.append(part)
            else:
                boundaries = [0] + [m.start() for m in scheme_matches] + [len(part)]
                for start, end in zip(boundaries, boundaries[1:], strict=False):
                    token = part[start:end].rstrip()
                    if token:
                        urls.append(token)
        elif _PARTIAL_SCHEME_RE.match(part):
            # Repair a truncated scheme (e.g. "ttps://" → "https://").
            if part.lower().startswith("ttps://") or part.lower().startswith("tps://"):
                repaired = "h" + part
            else:
                repaired = "ht" + part
            urls.append(repaired)
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
        if key == "propera implantació pap":
            return ""
    if waste_type == _WC_RESIDUAL:
        return _CS_DOOR_TO_DOOR
    return ""


def _map_fee_system(raw: str | None) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    return _FEE_SYSTEM_MAP.get(key, "")


def _normalise_frequency(raw: str) -> str:
    """Return the canonical BRIT CollectionFrequency name for *raw*.

    Looks up *raw* in ``_FREQUENCY_NORMALISE_MAP`` and returns the mapped
    value when a correction exists (e.g. ``xx per year`` → calculated count).
    Falls through unchanged for any string not listed in the map.
    """
    return _FREQUENCY_NORMALISE_MAP.get(raw, raw)


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
    if change_impl and change_year is not None:
        # change_year may be an int or a string like "2025/2026"
        year_str = (
            str(int(change_year))
            if isinstance(change_year, (int, float))
            and not isinstance(change_year, bool)
            else str(change_year).strip()
        )
        description_parts.append(f"Implementation change: {change_impl} ({year_str})")
    elif change_impl:
        description_parts.append(f"Implementation change: {change_impl}")

    return {
        "nuts_or_lau_id": lau_id,
        "country_code": _COUNTRY_CODE,
        "catchment_name": "",
        "collector_name": str(row[4] or "").strip(),
        "collection_system": collection_system,
        "waste_category": waste_type,
        "allowed_materials": "",
        "forbidden_materials": "",
        "fee_system": _map_fee_system(row[19]),
        "frequency": _normalise_frequency(str(row[17] or "").strip()),
        "connection_type": "",
        **_access_control_fields(row[14], collection_system),
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
        parser.add_argument(
            "--create-collectors",
            action="store_true",
            help=(
                "Create missing collectors on the target BRIT instance during the "
                "bulk import. Has no effect during a dry run."
            ),
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
        create_collectors: bool,
    ) -> dict:
        try:
            url = f"{api_url.rstrip('/')}/waste_collection/api/collection/import/"
            payload = json.dumps(
                {
                    "records": records,
                    "publication_status": publication_status,
                    "dry_run": dry_run,
                    "create_collectors": create_collectors,
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
        create_collectors = options.get("create_collectors", False)

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
            "collectors_created": 0,
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
                api_url,
                token,
                batch,
                publication_status,
                dry_run,
                create_collectors,
            )
            stats = result.get("stats", {})
            for key in (
                "created",
                "unchanged",
                "skipped",
                "collectors_created",
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
        self.stdout.write(f"  Collectors created:    {totals['collectors_created']}\n")
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
