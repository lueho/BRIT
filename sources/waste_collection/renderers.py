import re

from utils.file_export.renderers import BaseCSVRenderer, BaseXLSXRenderer


def _discover_dynamic_columns(data, static_keys):
    """Collect column keys from data rows that are not in the static label set."""
    dynamic = []
    seen = set(static_keys)
    for row in data:
        for key in row:
            if key not in seen:
                dynamic.append(key)
                seen.add(key)

    # Sort year-based columns to ensure chronological order
    dynamic = _sort_dynamic_columns(dynamic)
    return dynamic


def _sort_dynamic_columns(columns):
    """Sort dynamic columns, grouping year-based columns chronologically.

    Columns like 'population_2020', 'population_2021' should be ordered by year.
    The corresponding '_unit' columns are kept adjacent to their value columns.
    """
    # Pattern to match columns ending with a 4-digit year (and optional _unit suffix)
    year_pattern = re.compile(r"^(\w+?_)(\d{4})(_unit)?$")

    year_columns = {}  # base -> list of (year, is_unit, original_key)
    non_year_columns = []

    for col in columns:
        match = year_pattern.match(col)
        if match:
            base = match.group(1)  # e.g., 'population_', 'specific_waste_collected_'
            year = int(match.group(2))  # e.g., 2020, 2021
            is_unit = match.group(3) == "_unit"
            if base not in year_columns:
                year_columns[base] = []
            year_columns[base].append((year, is_unit, col))
        else:
            non_year_columns.append(col)

    # Sort year-based columns: by base name, then by year, with value before unit
    sorted_year_columns = []
    for base in sorted(year_columns.keys()):
        # Sort by year, then by is_unit (False before True, so value comes before unit)
        sorted_group = sorted(year_columns[base], key=lambda x: (x[0], x[1]))
        for _, _, col in sorted_group:
            sorted_year_columns.append(col)

    # Combine: non-year columns first (preserve original order), then sorted year columns
    return non_year_columns + sorted_year_columns


def _label_for_dynamic_key(key):
    """Generate a human-readable label for a dynamic column key."""
    return key.replace("_", " ").title()


_STATIC_LABELS = {
    "catchment": "Catchment",
    "nuts_or_lau_id": "NUTS/LAU Id",
    "country": "Country",
    "collector": "Collector",
    "collection_system": "Collection System",
    "bin_configuration": "Bin configuration",
    "waste_category": "Waste Category",
    "connection_type": "Connection type",
    "allowed_materials": "Allowed Materials",
    "forbidden_materials": "Forbidden Materials",
    "fee_system": "Fee System",
    "frequency": "Frequency",
    "min_bin_size": "Minimum bin size (L)",
    "required_bin_capacity": "Minimum required specific bin capacity (L/reference unit)",
    "required_bin_capacity_reference": "Reference unit for minimum required specific bin capacity",
    "established": "Year established",
    "comments": "Comments",
    "flyer_urls": "Weblinks",
    "bibliography_sources": "Bibliography Sources",
    "valid_from": "Valid from",
    "valid_until": "Valid until",
    "created_at": "Created at",
    "lastmodified_at": "Last modified at",
}

_TRAILING_STATIC_KEYS = [
    "comments",
    "flyer_urls",
    "bibliography_sources",
    "valid_from",
    "valid_until",
    "created_at",
    "lastmodified_at",
]

_LEADING_STATIC_KEYS = [
    key for key in _STATIC_LABELS if key not in _TRAILING_STATIC_KEYS
]


class CollectionXLSXRenderer(BaseXLSXRenderer):
    labels = dict(_STATIC_LABELS)
    workbook_options = {"constant_memory": True, "strings_to_urls": False}

    def render(self, file, data, *args, **kwargs):
        """Extend column list with dynamic property-value columns found in data."""
        dynamic = []
        labels = dict(_STATIC_LABELS)
        if data:
            dynamic = _discover_dynamic_columns(data, labels)
            for key in dynamic:
                labels[key] = _label_for_dynamic_key(key)
        self.column_order = _LEADING_STATIC_KEYS + dynamic + _TRAILING_STATIC_KEYS
        self.labels = labels
        super().render(file, data, *args, **kwargs)


class CollectionCSVRenderer(BaseCSVRenderer):
    writer_opts = {"delimiter": "\t"}
    header = _LEADING_STATIC_KEYS + _TRAILING_STATIC_KEYS
    labels = dict(_STATIC_LABELS)

    def render(self, file, data, *args, **kwargs):
        """Extend header with dynamic property-value columns found in data."""
        dynamic = []
        header = _LEADING_STATIC_KEYS + _TRAILING_STATIC_KEYS
        labels = dict(_STATIC_LABELS)
        if data:
            dynamic = _discover_dynamic_columns(data, labels)
            for key in dynamic:
                labels[key] = _label_for_dynamic_key(key)
        header = _LEADING_STATIC_KEYS + dynamic + _TRAILING_STATIC_KEYS
        self.header = header
        self.labels = labels
        super().render(file, data, *args, **kwargs)


__all__ = ["CollectionCSVRenderer", "CollectionXLSXRenderer"]
