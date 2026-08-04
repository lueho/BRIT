"""Template tags for the Waste Atlas generic map template."""

from django import template

from ..map_configs import MAP_CONFIGS
from ..models import WasteAtlasRenderingSettings

register = template.Library()

DATABASE_EDITABLE_OVERRIDE_KEYS = frozenset(
    {
        "exportLegendTitle",
        "exportLegendPlacement",
        "exportLegendWidth",
        "exportLegendColumns",
        "exportLegendFitContent",
        "exportLegendAvoidMapOverlap",
    }
)


def export_file_base(map_set, theme, prefix=None):
    """Derive the deterministic export file-name stem for a map page.

    Every Waste Atlas map export (SVG/PNG, plus the ``_change_<from>_<to>``
    suffix the renderer appends for change maps) is named from the page's
    structural identity: its map set (``selector_set``) and theme.  This keeps
    naming homogeneous across all maps without per-page or per-configuration
    ``fileBase`` values.

    Region-locked maps use ``waste_atlas_<set>_<theme>`` with the set
    lowercased and hyphens turned into underscores (``DE-NW`` → ``de_nw``);
    generic maps (no map set) use ``waste_atlas_<theme>``.
    """
    if prefix is None:
        prefix = WasteAtlasRenderingSettings.load().export_file_name_prefix
    set_slug = (map_set or "").strip().lower().replace("-", "_")
    theme_slug = (theme or "").strip()
    if set_slug:
        return f"{prefix}_{set_slug}_{theme_slug}"
    return f"{prefix}_{theme_slug}"


@register.simple_tag
def atlas_export_file_base(map_set, theme):
    """Template-friendly wrapper around :func:`export_file_base`."""
    return export_file_base(map_set, theme)


@register.simple_tag
def atlas_render_defaults():
    """Return the atlas-wide rendering and export defaults for the renderer."""
    return WasteAtlasRenderingSettings.load().client_defaults()


@register.simple_tag(takes_context=True)
def atlas_js_config(context, config_key):
    """Return the merged choropleth config dict for ``config_key``.

    Atlas-wide defaults from ``WasteAtlasRenderingSettings`` are exposed as
    ``renderDefaults`` and fill in the legend keys a map does not define.
    Database values from ``MAP_CONFIGS`` are merged with per-page overrides
    (``map_config_overrides``), runtime context (country, year, nutsPrefix,
    nutsLevel), and hard-coded DOM ids.  The result is intended to be passed
    through Django's ``json_script`` filter in the template for safe JSON
    injection.

    The export ``fileBase`` is always derived from the page's map set and
    theme (see :func:`export_file_base`); any stored or overridden
    ``fileBase`` is ignored so file naming stays homogeneous across maps.
    """
    settings = WasteAtlasRenderingSettings.load()
    config = dict(MAP_CONFIGS.get(config_key, {}))
    config.pop("fileBase", None)
    for key, value in (context.get("map_config_overrides") or {}).items():
        if key == "fileBase":
            continue
        if key not in DATABASE_EDITABLE_OVERRIDE_KEYS or key not in config:
            config[key] = value

    # DOM ids shared by every map
    config.setdefault("svgId", "atlas-svg")
    config.setdefault("containerId", "map-container")
    config.setdefault("loadingId", "loading-overlay")

    # Deterministic export file name — one rule for every map page.
    # Use the page's structural selector_set (None for generic maps), not the
    # runtime-resolved atlas_map_set which may default to a country for
    # generic pages.
    config["fileBase"] = export_file_base(
        context.get("atlas_page_selector_set"),
        context.get("atlas_active_theme"),
        prefix=settings.export_file_name_prefix,
    )

    # Atlas-wide rendering and export defaults, editable in the admin.
    defaults = settings.client_defaults()
    config["renderDefaults"] = defaults
    config.setdefault("noDataColor", defaults["noDataColor"])
    config.setdefault("legendPlacement", defaults["legend"]["placement"])
    config.setdefault("legendWidth", defaults["legend"]["width"])
    config.setdefault("legendFontSize", defaults["legend"]["fontSize"])

    # Runtime context from the view
    config["country"] = context.get("country", "DE")
    config["year"] = int(context.get("year", 2024))

    config.pop("nutsPrefix", None)
    nuts_prefix = context.get("nuts_prefix")
    if nuts_prefix:
        config["nutsPrefix"] = nuts_prefix

    config.pop("nutsLevel", None)
    nuts_level = context.get("nuts_level")
    if nuts_level:
        config["nutsLevel"] = int(nuts_level)

    collection_detail_category = context.get("collection_detail_category")
    if collection_detail_category and not context.get("from_year"):
        config["collectionDetailCategory"] = collection_detail_category

    # Change maps compare category or numeric value differences client-side
    config.pop("changeMode", None)
    config.pop("fromYear", None)
    from_year = context.get("from_year")
    if from_year:
        config["changeMode"] = True
        config["fromYear"] = int(from_year)

    return config
