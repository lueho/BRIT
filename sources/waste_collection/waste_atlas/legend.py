"""Single source of truth for export-legend configuration semantics.

The Waste Atlas export legend has five *independent* settings:

``placement``
    ``auto`` (choose automatically) or one of the fixed placements.
``mapLayout``
    ``auto`` (preserve the compatible layout), ``fit`` (reserve map space), or
    ``overlay`` (allow the legend over the map).
``columns``
    ``auto`` (choose automatically) or an exact count ``1``-``4``.
``itemFlow``
    ``column`` (fill one column after another) or ``row`` (fill across the
    columns, so entries read left to right).  The renderer applies the resolved
    arrangement to the on-screen legend as well, which keeps its own column
    count.
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
EXPORT_LEGEND_PLACEMENT_CHOICES = (
    (AUTO, "Automatic"),
    ("top-left", "Top left"),
    ("top", "Top"),
    ("top-right", "Top right"),
    ("right", "Right"),
    ("bottom-right", "Bottom right"),
    ("bottom", "Bottom"),
    ("bottom-left", "Bottom left"),
    ("left", "Left"),
)
EXPORT_LEGEND_PLACEMENTS = tuple(
    value for value, _label in EXPORT_LEGEND_PLACEMENT_CHOICES
)
FIXED_EXPORT_LEGEND_PLACEMENTS = EXPORT_LEGEND_PLACEMENTS[1:]
FIT_MAP = "fit"
OVERLAY_MAP = "overlay"
EXPORT_LEGEND_MAP_LAYOUT_CHOICES = (
    (AUTO, "Automatic"),
    (FIT_MAP, "Fit map around legend"),
    (OVERLAY_MAP, "Overlay legend on map"),
)
EXPORT_LEGEND_MAP_LAYOUTS = tuple(
    value for value, _label in EXPORT_LEGEND_MAP_LAYOUT_CHOICES
)
FIXED_EXPORT_LEGEND_COLUMNS = (1, 2, 3, 4)
# How legend entries are arranged across the columns.  These labelled choices
# are the single source of truth: the model field, the form select and
# ``normalize_item_flow`` all derive from them, so a new arrangement can never
# be selectable while the normalizer rejects it.
COLUMN_FLOW = "column"
ROW_FLOW = "row"
EXPORT_LEGEND_ITEM_FLOW_CHOICES = (
    (COLUMN_FLOW, "By column (fill one column, then the next)"),
    (ROW_FLOW, "By row (fill across the columns)"),
)
EXPORT_LEGEND_ITEM_FLOWS = tuple(
    value for value, _label in EXPORT_LEGEND_ITEM_FLOW_CHOICES
)

# Persisted flat keys that describe the export legend layout.
EXPORT_LEGEND_OVERRIDE_KEYS = (
    "exportLegendPlacement",
    "exportLegendMapLayout",
    "exportLegendColumns",
    "exportLegendItemFlow",
    "exportLegendWidth",
)
# Retired keys. Fitting width remains an invariant, map collision now uses the
# independent layout setting, and column counts are no longer coupled to
# placement, so these must never linger and silently affect a layout.
LEGACY_EXPORT_LEGEND_KEYS = (
    "exportLegendFitContent",
    "exportLegendAvoidMapOverlap",
    "exportLegendBottomColumns",
)

# Model bounds for the width fraction, mirrored here so resolution clamps to the
# same range the admin enforces.
MIN_WIDTH_FRACTION = 0.2
MAX_WIDTH_FRACTION = 0.9

# Legend entries a quartile map derives from the data instead of from its stored
# categories: the renderer classifies the values into quartiles and replaces the
# stored classes with these, so they are the entries such a legend actually shows
# and must be orderable like any other entry.  Their labels are the value ranges
# the renderer computes, so only the position is configurable.
QUARTILE_LEGEND_ENTRY_LABELS = (
    ("q1", "Lowest quarter (Q1)"),
    ("q2", "Second quarter (Q2)"),
    ("q3", "Third quarter (Q3)"),
    ("q4", "Highest quarter (Q4)"),
)


def quartile_legend_entries(configuration):
    """Return the quartile legend entries of ``configuration``, if it has any.

    Mirrors the renderer's condition for classifying into quartiles: a numeric
    field, a quartile palette and no explicit opt-out.
    """
    if not configuration.get("numericField"):
        return []
    colors = configuration.get("quartileColors") or []
    if not colors or configuration.get("enableQuartiles") is False:
        return []
    return [
        {
            "value": value,
            "label": label,
            "color": colors[index] if index < len(colors) else "",
        }
        for index, (value, label) in enumerate(QUARTILE_LEGEND_ENTRY_LABELS)
    ]


def order_legend_values(default_values, stored_order):
    """Return ``default_values`` rearranged by the saved ``stored_order``.

    A value the saved order does not mention keeps its position relative to the
    values it does mention: it stays directly behind the last mentioned value
    that precedes it in the default order, and in front of everything when no
    mentioned value precedes it.  A saved order therefore never scatters entries
    it knows nothing about — quartile classes stay where the default order puts
    them until they are ordered explicitly.
    """
    ranks = {}
    if isinstance(stored_order, (list, tuple)):
        ranks = {value: index for index, value in enumerate(stored_order)}
    keyed = []
    rank = -1
    offset = 0
    for value in default_values:
        if value in ranks:
            rank = ranks[value]
            offset = 0
        else:
            offset += 1
        keyed.append(((rank, offset), value))
    return [value for _key, value in sorted(keyed, key=lambda item: item[0])]


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


def normalize_map_layout(value):
    """Return a canonical map layout, or ``None`` when it means inherit."""
    if value is None:
        return None
    value = str(value).strip()
    if value in EXPORT_LEGEND_MAP_LAYOUTS:
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
    (``{"placement", "mapLayout", "columns", "itemFlow", "maxWidthFraction"}``)
    and is always fully populated, so the returned object never contains ``None``.
    """
    layers = (page_overrides or {}, stored or {})
    return {
        "placement": _resolve(
            "exportLegendPlacement",
            normalize_placement,
            layers,
            defaults["placement"],
        ),
        "mapLayout": _resolve(
            "exportLegendMapLayout",
            normalize_map_layout,
            layers,
            defaults["mapLayout"],
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
