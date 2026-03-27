#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

_DEFAULT_FILES = (
    Path("BRIT_Deutschland_Saarland_2024_SW.xlsx"),
    Path("BRIT_Deutschland_Sachsen_2024_SW.xlsx"),
    Path("BRIT_Deutschland_Sachsen-Anhalt_2024_SW.xlsx"),
)
_VALID_STATUSES = ("private", "review")
_BATCH_SIZE = 50
_PROP_SPECIFIC = 1
_PROP_TOTAL = 9
_PROP_CONN_RATE = 4
_UNIT_KG = "kg/(cap.*a)"
_UNIT_MG = "Mg/a"
_CONN_RATE_FALLBACK_UNIT = "% (of unknown reference)"
_BROKEN_WEBARCHIVE_RE = re.compile(
    r"(https?://web\.archive\.org/web/\d{6}),\s*(\d{6,}/https?://)",
    re.IGNORECASE,
)
_URL_START_RE = re.compile(r"https?://", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_FIELD_ALIASES = {
    "catchment_name": ("Catchment",),
    "nuts_or_lau_id": ("NUTS/LAU Id",),
    "collector": ("Collector",),
    "collection_system": ("Collection System",),
    "waste_category": ("Waste Category",),
    "established": ("Introduction of collection system (Year)",),
    "connection_type": ("Connection type",),
    "allowed_materials": ("Allowed Materials",),
    "forbidden_materials": ("Forbidden Materials",),
    "fee_system": ("Fee System",),
    "frequency": ("Frequency",),
    "min_bin_size": ("Minimum bin size (L)",),
    "required_bin_capacity": (
        "Minimum required specific bin capacity (L/reference unit)",
    ),
    "required_bin_capacity_reference": (
        "Reference unit for minimum required specific bin capacity",
    ),
    "description": ("Comments",),
    "valid_from": ("Valid from",),
    "valid_until": ("Valid until",),
}
_SOURCE_COLUMNS = (
    "Weblinks",
    "Sources_new",
    "Bibliography Sources",
)
_SPECIFIC_UNIT_ALIASES = {
    "kg/(cap.*a)": (_PROP_SPECIFIC, _UNIT_KG),
    "kg/(cap*a)": (_PROP_SPECIFIC, _UNIT_KG),
}
_TOTAL_UNIT_ALIASES = {
    "mg/a": (_PROP_TOTAL, _UNIT_MG),
    "t/a": (_PROP_TOTAL, _UNIT_MG),
}
_CONNECTION_RATE_UNIT_ALIASES = {
    "% residential properties": "% of residential properties",
}


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _normalize_header_name(value) -> str | None:
    return _normalize_text(value)


def _build_header_index(header_row) -> dict[str, int]:
    header_index = {}
    for index, value in enumerate(header_row):
        name = _normalize_header_name(value)
        if name:
            header_index[name] = index
    return header_index


def _header_position(header_index: dict[str, int], key: str) -> int | None:
    aliases = _FIELD_ALIASES.get(key, (key,))
    for alias in aliases:
        normalized = _normalize_header_name(alias)
        if normalized in header_index:
            return header_index[normalized]
    return None


def _row_value(row, header_index: dict[str, int], key: str):
    index = _header_position(header_index, key)
    if index is None or index >= len(row):
        return None
    return row[index]


def _safe_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        compact = text.replace(" ", "")
        if compact.count(",") == 1 and compact.count(".") == 0:
            compact = compact.replace(",", ".")
        try:
            return float(compact)
        except ValueError:
            return None
    return None


def _to_decimal_or_none(value) -> float | None:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, 1)


def _to_int_or_none(value) -> int | None:
    number = _safe_float(value)
    if number is None:
        return None
    return int(number)


def _resolve_date(value):
    if value is None:
        return None
    if hasattr(value, "date") and callable(value.date):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            try:
                return datetime.fromisoformat(text).date().isoformat()
            except ValueError:
                return None
    return None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _split_source_cell(raw) -> tuple[list[str], list[str]]:
    text = _normalize_text(raw)
    if not text:
        return [], []

    text = _BROKEN_WEBARCHIVE_RE.sub(r"\1\2", text)
    urls = [match.group(0).strip(" ,;") for match in _URL_RE.finditer(text)]
    notes_text = _URL_RE.sub(" ", text)
    notes_text = re.sub(r"\s*,\s*,+\s*", ", ", notes_text)
    notes_text = re.sub(r"\s{2,}", " ", notes_text).strip(" ,;")
    notes = [notes_text] if notes_text else []
    return urls, notes


def _collect_source_entries(
    row, header_index: dict[str, int]
) -> tuple[list[str], list[str]]:
    urls = []
    notes = []
    for column_name in _SOURCE_COLUMNS:
        raw = _row_value(row, header_index, column_name)
        if not raw:
            continue
        column_urls, column_notes = _split_source_cell(raw)
        urls.extend(column_urls)
        notes.extend(column_notes)
    return _dedupe_preserve_order(urls), _dedupe_preserve_order(notes)


def _normalize_amount_unit(raw_unit):
    unit = _normalize_text(raw_unit)
    if unit is None:
        return None
    lowered = unit.lower()
    if lowered in _SPECIFIC_UNIT_ALIASES:
        return _SPECIFIC_UNIT_ALIASES[lowered]
    if lowered in _TOTAL_UNIT_ALIASES:
        return _TOTAL_UNIT_ALIASES[lowered]
    return None


def _normalize_connection_rate_unit(raw_unit) -> str | None:
    unit = _normalize_text(raw_unit)
    if unit is None:
        return None
    return _CONNECTION_RATE_UNIT_ALIASES.get(unit.lower(), unit)


def _append_warning(warnings: list[str] | None, message: str) -> None:
    if warnings is not None:
        warnings.append(message)


def _collect_property_values(
    row,
    header_index: dict[str, int],
    row_label: str,
    warnings: list[str] | None = None,
) -> list[dict]:
    property_values = []

    for year in range(2020, 2025):
        value = _safe_float(_row_value(row, header_index, f"Connection Rate {year}"))
        if value is None:
            continue
        raw_unit = _row_value(row, header_index, f"Connection Rate {year} Unit")
        unit_name = (
            _normalize_connection_rate_unit(raw_unit) or _CONN_RATE_FALLBACK_UNIT
        )
        property_values.append(
            {
                "property_id": _PROP_CONN_RATE,
                "unit_name": unit_name,
                "year": year,
                "average": value,
            }
        )

    for year in range(2015, 2025):
        value = _safe_float(
            _row_value(row, header_index, f"Specific Waste Collected {year}")
        )
        if value is None:
            continue
        raw_unit = _row_value(
            row, header_index, f"Specific Waste Collected {year} Unit"
        )
        normalized = _normalize_amount_unit(raw_unit)
        if normalized is None:
            _append_warning(
                warnings,
                f"{row_label}: skipped Specific Waste Collected {year} because unit '{_normalize_text(raw_unit) or ''}' is not supported.",
            )
            continue
        property_id, unit_name = normalized
        property_values.append(
            {
                "property_id": property_id,
                "unit_name": unit_name,
                "year": year,
                "average": value,
            }
        )

    return property_values


def _row_to_record(
    row,
    header_index: dict[str, int],
    row_label: str,
    warnings: list[str] | None = None,
) -> dict:
    flyer_urls, sources = _collect_source_entries(row, header_index)
    return {
        "nuts_or_lau_id": _row_value(row, header_index, "nuts_or_lau_id") or "",
        "catchment_name": _row_value(row, header_index, "catchment_name") or "",
        "collector_name": _row_value(row, header_index, "collector") or "",
        "collection_system": _row_value(row, header_index, "collection_system") or "",
        "waste_category": _row_value(row, header_index, "waste_category") or "",
        "established": _to_int_or_none(_row_value(row, header_index, "established")),
        "allowed_materials": _row_value(row, header_index, "allowed_materials") or "",
        "forbidden_materials": _row_value(row, header_index, "forbidden_materials")
        or "",
        "fee_system": _row_value(row, header_index, "fee_system") or "",
        "frequency": _row_value(row, header_index, "frequency") or "",
        "connection_type": _row_value(row, header_index, "connection_type") or "",
        "min_bin_size": _to_decimal_or_none(
            _row_value(row, header_index, "min_bin_size")
        ),
        "required_bin_capacity": _to_decimal_or_none(
            _row_value(row, header_index, "required_bin_capacity")
        ),
        "required_bin_capacity_reference": _row_value(
            row, header_index, "required_bin_capacity_reference"
        )
        or "",
        "description": _row_value(row, header_index, "description") or "",
        "valid_from": _resolve_date(_row_value(row, header_index, "valid_from")),
        "valid_until": _resolve_date(_row_value(row, header_index, "valid_until")),
        "sources": sources,
        "flyer_urls": flyer_urls,
        "property_values": _collect_property_values(
            row,
            header_index,
            row_label=row_label,
            warnings=warnings,
        ),
    }


def _load_records(file_path: Path) -> tuple[list[dict], list[str], int]:
    workbook = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    header_row = next(rows, None)
    if header_row is None:
        return [], [f"{file_path.name}: workbook is empty."], 0

    header_index = _build_header_index(header_row)
    records = []
    warnings = []
    row_count = 0

    for row_number, row in enumerate(rows, start=2):
        row_count += 1
        row_label = f"{file_path.name} row {row_number}"
        record = _row_to_record(
            row, header_index, row_label=row_label, warnings=warnings
        )
        missing = []
        if not record.get("collection_system"):
            missing.append("collection_system")
        if not record.get("valid_from"):
            missing.append("valid_from")
        if missing:
            warnings.append(
                f"{row_label}: skipped because required field(s) are missing: {', '.join(missing)}"
            )
            continue
        records.append(record)

    return records, warnings, row_count


def _read_json(req: Request, timeout: int) -> dict:
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def get_token(api_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode()
    errors = []
    for endpoint in ("/api/auth/token/", "/api-token-auth/"):
        url = f"{api_url.rstrip('/')}{endpoint}"
        req = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            data = _read_json(req, timeout=30)
            token = data.get("token")
            if token:
                return token
            errors.append(f"{endpoint}: no token in response {data}")
        except HTTPError as exc:
            errors.append(f"{endpoint}: HTTP {exc.code} {exc.read().decode()}")
        except URLError as exc:
            errors.append(f"{endpoint}: {exc}")
    sys.exit("Could not obtain token: " + " | ".join(errors))


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
        return _read_json(req, timeout=120)
    except HTTPError as exc:
        body = exc.read().decode()
        sys.exit(f"API request failed ({exc.code}): {body}")


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


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Import improved German 2024 waste collection workbooks via the BRIT API."
    )
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        help="Path to an Excel file. Provide multiple times to import multiple workbooks.",
    )
    parser.add_argument(
        "--api-url",
        required=True,
        help="Base URL of the BRIT instance, e.g. http://localhost:8000",
    )
    parser.add_argument("--token", default=None, help="DRF auth token.")
    parser.add_argument(
        "--username", default=None, help="Username used to obtain a token."
    )
    parser.add_argument(
        "--password", default=None, help="Password used to obtain a token."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without writing."
    )
    parser.add_argument(
        "--publication-status",
        default="private",
        choices=_VALID_STATUSES,
    )
    parser.add_argument("--batch-size", type=int, default=_BATCH_SIZE)
    return parser.parse_args()


def main():
    args = _parse_args()
    if args.batch_size <= 0:
        sys.exit("--batch-size must be greater than 0.")

    token = args.token
    if not token:
        if not args.username or not args.password:
            sys.exit("Provide --token or both --username and --password.")
        token = get_token(args.api_url, args.username, args.password)
        print("Token obtained.")

    file_paths = (
        [Path(path) for path in args.file] if args.file else list(_DEFAULT_FILES)
    )
    for file_path in file_paths:
        if not file_path.exists():
            sys.exit(f"Excel file not found: {file_path}")

    if args.dry_run:
        print("DRY RUN — no records will be written.")

    all_records = []
    local_warnings = []
    for file_path in file_paths:
        records, warnings, row_count = _load_records(file_path)
        all_records.extend(records)
        local_warnings.extend(warnings)
        print(
            f"Loaded {len(records)} valid record(s) from {file_path.name} ({row_count} data row(s))."
        )

    totals = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": len(
            [
                warning
                for warning in local_warnings
                if "skipped because required field(s) are missing" in warning
            ]
        ),
        "predecessor_links": 0,
        "cpv_created": 0,
        "cpv_unchanged": 0,
        "cpv_skipped": 0,
        "flyers_created": 0,
        "sources_created": 0,
        "warnings": [],
        "unresolved_frequencies": {},
    }

    batches = [
        all_records[index : index + args.batch_size]
        for index in range(0, len(all_records), args.batch_size)
    ]

    for batch_number, batch in enumerate(batches, start=1):
        print(
            f"  Posting batch {batch_number}/{len(batches)} ({len(batch)} records)…",
            end=" ",
            flush=True,
        )
        result = post_batch(
            args.api_url,
            token,
            batch,
            args.publication_status,
            args.dry_run,
        )
        stats = result.get("stats", {})
        for key in (
            "created",
            "updated",
            "unchanged",
            "skipped",
            "predecessor_links",
            "cpv_created",
            "cpv_unchanged",
            "cpv_skipped",
            "flyers_created",
            "sources_created",
        ):
            totals[key] += stats.get(key, 0)
        totals["warnings"].extend(stats.get("warnings", []))
        _merge_unresolved_frequencies(
            totals["unresolved_frequencies"],
            stats.get("unresolved_frequencies", {}),
        )
        print(
            f"created={stats.get('created', 0)} updated={stats.get('updated', 0)} unchanged={stats.get('unchanged', 0)} skipped={stats.get('skipped', 0)}"
        )

    print("\n=== Import Summary ===")
    print(f"  Collections created:  {totals['created']}")
    print(f"  Collections updated:  {totals['updated']}")
    print(f"  Collections unchanged:{totals['unchanged']:>4}")
    print(f"  Collections skipped:  {totals['skipped']}")
    print(f"  Predecessor links:    {totals['predecessor_links']}")
    print(f"  CPVs created:         {totals['cpv_created']}")
    print(f"  CPVs unchanged:       {totals['cpv_unchanged']}")
    print(f"  CPVs skipped:         {totals['cpv_skipped']}")
    print(f"  Flyers created:       {totals['flyers_created']}")
    print(f"  Sources created:      {totals['sources_created']}")

    all_warnings = local_warnings + totals["warnings"]
    if all_warnings:
        print(f"\n  Warnings ({len(all_warnings)}):")
        for warning in all_warnings:
            print(f"    {warning}")

    if totals["unresolved_frequencies"]:
        print("\n  Unresolved frequencies (manual fix after sync):")
        unresolved_items = sorted(
            totals["unresolved_frequencies"].items(),
            key=lambda item: (-int(item[1].get("count", 0)), item[0]),
        )
        for frequency_name, details in unresolved_items:
            print(
                f"    {frequency_name} (count={details.get('count', 0)}, reason={details.get('reason', 'not_found')})"
            )


if __name__ == "__main__":
    main()
