"""Single source of truth for export-legend configuration semantics.

The Waste Atlas export legend has four *independent* settings:

``placement``
    ``auto`` (choose automatically) or one of the fixed placements.
``columns``
    ``auto`` (choose automatically) or an exact count ``1``-``4``.
``itemFlow``
    ``column`` (fill one column after another) or ``row`` (fill across the
    columns, so entries read left to right).
``maxWidthFraction``
    A hard upper bound on legend width as a fraction of the page; the
    renderer measures content and never uses more width than needed, so the
    actual width may be smaller.

Each setting is resolved with explicit *inherit / auto / fixed* semantics:

* a **missing** key inherits from the next layer,
* an explicit ``auto`` value means "decide automatically",
* a concrete value is a fixed constraint.

Precedence, highest first: **page/region override -> stored theme config ->
atlas defaults**.  A page/region override is a deliberate escape hatch for a
single problematic page; because one theme configuration serves many regional
pages, that override must win over the shared theme configuration.
"""

AUTO = "auto"

# Fixed placements a user (or override) may pin the legend to.
FIXED_EXPORT_LEGEND_PLACEMENTS = (
    "right",
    "left",
    "bottom",
    "bottom-right",
    "bottom-left",
    "top-right",
    "top-left",
)
EXPORT_LEGEND_PLACEMENTS = (AUTO, *FIXED_EXPORT_LEGEND_PLACEMENTS)
FIXED_EXPORT_LEGEND_COLUMNS = (1, 2, 3, 4)
# How legend entries are arranged across the columns.
COLUMN_FLOW = "column"
ROW_FLOW = "row"
EXPORT_LEGEND_ITEM_FLOWS = (COLUMN_FLOW, ROW_FLOW)

# Persisted flat keys that describe the export legend layout.
EXPORT_LEGEND_OVERRIDE_KEYS = (
    "exportLegendPlacement",
    "exportLegendColumns",
    "exportLegendItemFlow",
    "exportLegendWidth",
)
# Retired keys.  "Fit width to content" and "avoid map overlap" are now hard
# layout invariants rather than options, and column counts are no longer coupled
# to placement, so these must never linger and silently affect a layout.
LEGACY_EXPORT_LEGEND_KEYS = (
    "exportLegendFitContent",
    "exportLegendAvoidMapOverlap",
    "exportLegendBottomColumns",
)

# Model bounds for the width fraction, mirrored here so resolution clamps to the
# same range the admin enforces.
MIN_WIDTH_FRACTION = 0.2
MAX_WIDTH_FRACTION = 0.9


def normalize_placement(value):
    """Return a canonical placement, or ``None`` when the value means inherit."""
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    if value == AUTO:
        return AUTO
    if value in FIXED_EXPORT_LEGEND_PLACEMENTS:
        return value
    return None


def normalize_columns(value):
    """Return ``auto`` or an exact column count, or ``None`` (inherit)."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
        if value == AUTO:
            return AUTO
    if value == AUTO:
        return AUTO
    try:
        columns = int(value)
    except (TypeError, ValueError):
        return None
    if columns in FIXED_EXPORT_LEGEND_COLUMNS:
        return columns
    return None


def normalize_item_flow(value):
    """Return a canonical item flow, or ``None`` when the value means inherit."""
    if value is None:
        return None
    value = str(value).strip()
    if value in EXPORT_LEGEND_ITEM_FLOWS:
        return value
    return None


def normalize_width_fraction(value):
    """Return a clamped width fraction, or ``None`` when it means inherit."""
    if value is None or value == "":
        return None
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return None
    if fraction <= 0:
        return None
    return max(MIN_WIDTH_FRACTION, min(MAX_WIDTH_FRACTION, fraction))


def _resolve(key, normalize, layers, fallback):
    """Return the first valid value for ``key`` across ``layers`` in order."""
    for layer in layers:
        if not layer or key not in layer:
            continue
        resolved = normalize(layer.get(key))
        if resolved is not None:
            return resolved
    return fallback


def resolve_export_legend(*, stored, page_overrides, defaults):
    """Resolve the one effective export-legend config the renderer consumes.

    ``defaults`` is the atlas-level fallback object
    (``{"placement", "columns", "itemFlow", "maxWidthFraction"}``) and is always
    fully populated, so the returned object never contains ``None``.
    """
    layers = (page_overrides or {}, stored or {})
    return {
        "placement": _resolve(
            "exportLegendPlacement",
            normalize_placement,
            layers,
            defaults["placement"],
        ),
        "columns": _resolve(
            "exportLegendColumns",
            normalize_columns,
            layers,
            defaults["columns"],
        ),
        "itemFlow": _resolve(
            "exportLegendItemFlow",
            normalize_item_flow,
            layers,
            defaults["itemFlow"],
        ),
        "maxWidthFraction": _resolve(
            "exportLegendWidth",
            normalize_width_fraction,
            layers,
            defaults["maxWidthFraction"],
        ),
    }
