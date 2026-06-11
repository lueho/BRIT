"""Region/theme selection registry for the Waste Atlas map selector.

``WASTE_ATLAS_MAP_SELECTIONS`` is derived from the page registry in
``pages.py`` so that every routed map page automatically appears in the
selector with a consistent label.
"""

from .pages import MAP_PAGES, MAP_SET_LABELS

# Short selector label per theme key.
THEME_LABELS = {
    "access_control": "Access control",
    "bin_configuration": "Bin configuration",
    "biowaste_collection_amount": "Biowaste amount",
    "biowaste_collection_count": "Biowaste collection count",
    "biowaste_collection_point_count": "Biowaste collection points",
    "biowaste_collection_system": "Biowaste collection system",
    "biowaste_fee_system": "Biowaste fees",
    "biowaste_frequency": "Biowaste schedule",
    "biowaste_impurity": "Biowaste impurity",
    "biowaste_min_bin_size": "Biowaste bin size",
    "biowaste_required_bin_capacity": "Biowaste bin capacity",
    "collection_count_ratio": "Collection-count ratio",
    "collection_orga_level": "Collections: administrative level",
    "collection_point_count": "Collection points",
    "collection_point_count_ratio": "Collection-point ratio",
    "collection_support": "Collection aids",
    "collection_system": "Biowaste collection systems",
    "combined_collection_count": "Combined collection count",
    "combined_collection_system": "Combined collection system",
    "combined_fee_system": "Combined fees",
    "combined_frequency": "Combined schedule",
    "connection_rate": "Connection rate",
    "food_waste_category": "Accepted food waste",
    "green_waste_collection_amount": "Green waste amount",
    "green_waste_collection_system_count": "Green waste system count",
    "min_bin_size_ratio": "Minimum bin-size ratio",
    "orga_level": "Collectors: administrative level",
    "organic_collection_amount": "Organic-fraction amount",
    "organic_waste_ratio": "Organic-fraction share",
    "paper_bags": "Paper products",
    "plastic_bags": "Plastic bags",
    "population_density": "Population density",
    "residual_collection_amount": "Residual waste amount",
    "residual_collection_count": "Residual waste collection count",
    "residual_collection_point_count": "Residual waste collection points",
    "residual_collection_system": "Residual waste collection system",
    "residual_fee_system": "Residual waste fees",
    "residual_frequency": "Residual waste schedule",
    "residual_min_bin_size": "Residual waste bin size",
    "residual_required_bin_capacity": "Residual waste bin capacity",
    "system_access_control": "System + access/use control",
    "waste_ratio": "Amount ratio",
    "weekly_bp_access_days": "Bring-point access days",
}


def _build_selections():
    """Build the map-set/theme selection registry from ``MAP_PAGES``."""
    selections = {}
    for page in MAP_PAGES:
        map_set = page["selector_set"]
        if not map_set:
            continue
        themes = selections.setdefault(
            map_set, {"label": MAP_SET_LABELS[map_set], "themes": {}}
        )["themes"]
        themes[page["theme"]] = {
            "label": THEME_LABELS[page["theme"]],
            "route_name": page["name"],
        }
    return dict(sorted(selections.items()))


WASTE_ATLAS_MAP_SELECTIONS = _build_selections()

MAP_SELECTION_YEARS = ("2020", "2021", "2022", "2023", "2024")

MAP_SELECTION_THEME_ORDER = {
    "orga_level": 10,
    "collection_orga_level": 11,
    "population_density": 20,
    "collection_system": 100,
    "food_waste_category": 110,
    "paper_bags": 120,
    "plastic_bags": 130,
    "collection_support": 140,
    "residual_min_bin_size": 150,
    "biowaste_min_bin_size": 160,
    "residual_required_bin_capacity": 170,
    "biowaste_required_bin_capacity": 180,
    "collection_point_count": 190,
    "biowaste_collection_point_count": 200,
    "residual_collection_point_count": 210,
    "green_waste_collection_system_count": 220,
    "residual_frequency": 300,
    "biowaste_frequency": 310,
    "combined_frequency": 320,
    "residual_collection_count": 400,
    "biowaste_collection_count": 410,
    "combined_collection_count": 420,
    "collection_count_ratio": 430,
    "collection_point_count_ratio": 440,
    "residual_fee_system": 500,
    "biowaste_fee_system": 510,
    "combined_fee_system": 520,
    "residual_collection_amount": 600,
    "biowaste_collection_amount": 610,
    "green_waste_collection_amount": 620,
    "organic_collection_amount": 630,
    "waste_ratio": 640,
    "organic_waste_ratio": 650,
    "connection_rate": 700,
}

MAP_SELECTION_WASTE_CATEGORIES = {
    "general": "General / not waste-specific",
    "residual": "Residual waste",
    "biowaste": "Biowaste",
    "green_waste": "Green waste",
    "organic": "Organic fraction",
    "combined": "Combined waste categories",
}

MAP_SELECTION_THEME_LABELS = {
    "collection_amount": "Collected amount",
    "collection_count": "Collection count",
    "collection_point_count": "Collection points",
    "collection_system": "Collection system",
    "collection_system_count": "Collection system count",
    "fee_system": "Fees",
    "frequency": "Schedule",
    "min_bin_size": "Bin size",
    "required_bin_capacity": "Bin capacity",
}

MAP_SELECTION_WASTE_CATEGORY_PREFIXES = (
    ("green_waste_", "green_waste"),
    ("residual_", "residual"),
    ("biowaste_", "biowaste"),
    ("organic_", "organic"),
    ("combined_", "combined"),
)

MAP_SELECTION_WASTE_CATEGORY_OVERRIDES = {
    "collection_system": "biowaste",
    "connection_rate": "biowaste",
    "food_waste_category": "biowaste",
    "paper_bags": "biowaste",
    "plastic_bags": "biowaste",
    "collection_support": "biowaste",
}


def _selection_waste_category(theme):
    if theme in MAP_SELECTION_WASTE_CATEGORY_OVERRIDES:
        return MAP_SELECTION_WASTE_CATEGORY_OVERRIDES[theme]
    for prefix, waste_category in MAP_SELECTION_WASTE_CATEGORY_PREFIXES:
        if theme.startswith(prefix):
            return waste_category
    return "general"


def _selection_theme_group(theme):
    for prefix, _waste_category in MAP_SELECTION_WASTE_CATEGORY_PREFIXES:
        if theme.startswith(prefix):
            return theme.removeprefix(prefix)
    return theme


def _selection_theme_label(theme, theme_selection):
    theme_group = _selection_theme_group(theme)
    return MAP_SELECTION_THEME_LABELS.get(theme_group, theme_selection["label"])


def _theme_sort_key(theme_item):
    theme, theme_selection = theme_item
    return (
        MAP_SELECTION_THEME_ORDER.get(theme, 1000),
        theme_selection["label"],
    )


def build_map_selection_context(
    reverse_func, selected_map_set="DE", selected_theme="orga_level"
):
    map_sets = []
    themes_by_map_set = {}
    for map_set, map_selection in WASTE_ATLAS_MAP_SELECTIONS.items():
        themes_by_map_set[map_set] = [
            {
                "value": theme,
                "theme_group": _selection_theme_group(theme),
                "waste_category": _selection_waste_category(theme),
                "label": _selection_theme_label(theme, theme_selection),
                "url": reverse_func(theme_selection["route_name"]),
                "change_url": reverse_func(
                    "waste-atlas-change-map", args=[map_set, theme]
                ),
            }
            for theme, theme_selection in sorted(
                map_selection["themes"].items(), key=_theme_sort_key
            )
        ]
        map_sets.append(
            {
                "value": map_set,
                "label": map_selection["label"],
                "selected": map_set == selected_map_set,
            }
        )
    return {
        "map_selection_map_sets": map_sets,
        "map_selection_themes_by_map_set": themes_by_map_set,
        "map_selection_waste_categories": MAP_SELECTION_WASTE_CATEGORIES,
        "map_selection_years": MAP_SELECTION_YEARS,
        "selected_map_set": selected_map_set,
        "selected_map_theme": selected_theme,
        "selected_waste_category": _selection_waste_category(selected_theme),
    }
