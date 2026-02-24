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
    return dynamic


def _label_for_dynamic_key(key):
    """Generate a human-readable label for a dynamic column key."""
    return key.replace("_", " ").title()


# Static labels shared by both renderers.
_STATIC_LABELS = {
    "catchment": "Catchment",
    "nuts_or_lau_id": "NUTS/LAU Id",
    "country": "Country",
    "collector": "Collector",
    "collection_system": "Collection System",
    "waste_category": "Waste Category",
    "connection_type": "Connection type",
    "allowed_materials": "Allowed Materials",
    "forbidden_materials": "Forbidden Materials",
    "fee_system": "Fee System",
    "frequency": "Frequency",
    "min_bin_size": "Minimum bin size (L)",
    "required_bin_capacity": "Minimum required specific bin capacity (L/reference unit)",
    "required_bin_capacity_reference": "Reference unit for minimum required specific bin capacity",
    "comments": "Comments",
    "flyer_urls": "Flyer URLs",
    "bibliography_sources": "Bibliography Sources",
    "valid_from": "Valid from",
    "valid_until": "Valid until",
    "created_at": "Created at",
    "lastmodified_at": "Last modified at",
}


class CollectionXLSXRenderer(BaseXLSXRenderer):
    labels = dict(_STATIC_LABELS)
    workbook_options = {"constant_memory": True, "strings_to_urls": False}

    def render(self, file, data, *args, **kwargs):
        """Extend column list with dynamic property-value columns found in data."""
        labels = dict(_STATIC_LABELS)
        if data:
            dynamic = _discover_dynamic_columns(data, labels)
            for key in dynamic:
                labels[key] = _label_for_dynamic_key(key)
            self.column_order = list(_STATIC_LABELS.keys()) + dynamic
        self.labels = labels
        super().render(file, data, *args, **kwargs)


class CollectionCSVRenderer(BaseCSVRenderer):
    writer_opts = {"delimiter": "\t"}
    header = list(_STATIC_LABELS.keys())
    labels = dict(_STATIC_LABELS)

    def render(self, file, data, *args, **kwargs):
        """Extend header with dynamic property-value columns found in data."""
        header = list(_STATIC_LABELS.keys())
        labels = dict(_STATIC_LABELS)
        if data:
            dynamic = _discover_dynamic_columns(data, labels)
            for key in dynamic:
                labels[key] = _label_for_dynamic_key(key)
            header.extend(dynamic)
        self.header = header
        self.labels = labels
        super().render(file, data, *args, **kwargs)
