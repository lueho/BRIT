"""Chart registry for the Waste Atlas statistics dashboard.

The dashboard is generated from the same two sources as the maps themselves —
the page registry (``pages.py``) and the stored map configurations
(``map_configs.py``) — so every chart shows exactly the classification,
labels, palette and API endpoint of the map page it links to. Adding a map
page therefore adds its chart; no chart is configured by hand.
"""

from .map_configs import MAP_CONFIGS
from .map_selection import (
    DIRECTORY_SECTION_LABELS,
    DIRECTORY_SECTION_ORDER,
    MAP_SELECTION_THEME_ORDER,
    MAP_SELECTION_WASTE_CATEGORIES,
    MAP_SELECTION_YEARS,
    MAP_SET_REGION_SCOPES,
    THEME_LABELS,
    _directory_section,
    _selection_waste_category,
)
from .pages import MAP_PAGES, MAP_SET_LABELS

DASHBOARD_DEFAULT_MAP_SET = "DE"

# Keys copied verbatim from a stored map configuration into a chart config.
_CHART_CONFIG_KEYS = (
    "dataUrl",
    "dataField",
    "categories",
    "noDataColor",
    "noDataLabel",
    "legendTitle",
    "numericField",
    "transformName",
)


def resolve_map_set(map_set):
    """Return a known map set, falling back to the dashboard default."""
    if map_set in MAP_SET_REGION_SCOPES:
        return map_set
    return DASHBOARD_DEFAULT_MAP_SET


def resolve_year(year):
    """Return a selectable year as an int, falling back to the latest one."""
    if str(year) in MAP_SELECTION_YEARS:
        return int(year)
    return int(MAP_SELECTION_YEARS[-1])


def resolve_category(category):
    """Return a known waste category, or the empty string for "all"."""
    return category if category in MAP_SELECTION_WASTE_CATEGORIES else ""


def _chartable_pages(map_set):
    """Return the map set's pages that have a chartable stored configuration."""
    configs = dict(MAP_CONFIGS.items())
    pages = []
    seen_themes = set()
    for page in MAP_PAGES:
        theme = page["theme"]
        if page["selector_set"] != map_set or theme in seen_themes:
            continue
        config = configs.get(page["config_key"], {})
        if not config.get("dataUrl") or not config.get("categories"):
            continue
        seen_themes.add(theme)
        pages.append((page, config))
    pages.sort(
        key=lambda item: (
            MAP_SELECTION_THEME_ORDER.get(item[0]["theme"], 1000),
            item[0]["theme"],
        )
    )
    return pages


def _chart_config(page, config, reverse_func):
    """Build one chart config from a map page and its stored map config."""
    theme = page["theme"]
    chart = {
        "theme": theme,
        "chartId": f"dashboard-chart-{theme}",
        "title": THEME_LABELS.get(theme, theme),
        "mapTitle": page["title"],
        "mapUrl": reverse_func(page["name"]),
        "section": _directory_section(theme),
        "wasteCategory": _selection_waste_category(theme),
    }
    for key in _CHART_CONFIG_KEYS:
        if key in config:
            chart[key] = config[key]
    return chart


def build_dashboard_context(reverse_func, map_set=None, year=None, category=""):
    """Build the dashboard context for one region, year and waste category.

    The returned ``dashboard_config`` is the payload for the chart renderer:
    the region scope and year every chart request is made with, plus one chart
    config per map page of the region.
    """
    map_set = resolve_map_set(map_set)
    year = resolve_year(year)
    category = resolve_category(category)
    scope = MAP_SET_REGION_SCOPES[map_set]

    charts = [
        _chart_config(page, config, reverse_func)
        for page, config in _chartable_pages(map_set)
    ]
    charts_by_section = {}
    for chart in charts:
        charts_by_section.setdefault(chart["section"], []).append(chart)
    sections = [
        {
            "key": key,
            "label": DIRECTORY_SECTION_LABELS[key],
            "panels": charts_by_section[key],
        }
        for key in DIRECTORY_SECTION_ORDER
        if key in charts_by_section
    ]

    config = {
        "mapSet": map_set,
        "mapSetLabel": MAP_SET_LABELS.get(map_set, map_set),
        "country": scope["country"],
        "nutsPrefix": scope["nuts_prefix"],
        "nutsLevel": scope["nuts_level"],
        "year": year,
        "years": [int(value) for value in MAP_SELECTION_YEARS],
        "wasteCategory": category,
        "panels": charts,
    }

    return {
        "dashboard_map_set": map_set,
        "dashboard_map_set_label": config["mapSetLabel"],
        "dashboard_map_sets": [
            {"value": value, "label": MAP_SET_LABELS.get(value, value)}
            for value in sorted(MAP_SET_REGION_SCOPES)
        ],
        "dashboard_year": year,
        "dashboard_years": list(MAP_SELECTION_YEARS),
        "dashboard_categories": MAP_SELECTION_WASTE_CATEGORIES,
        "dashboard_selected_category": category,
        "dashboard_sections": sections,
        "dashboard_config": config,
    }
