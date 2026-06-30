"""Region/theme selection registry for the Waste Atlas map selector.

``WASTE_ATLAS_MAP_SELECTIONS`` is derived from the page registry in
``pages.py`` so that every routed map page automatically appears in the
selector with a consistent label.
"""

from urllib.parse import urlencode

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
    "participation_policy": "Participation Policy",
    "food_waste_category": "Accepted food waste",
    "green_waste_collection_amount": "Green waste amount",
    "green_waste_collection_system_count": "Green waste system count",
    "min_bin_size_ratio": "Minimum bin-size ratio",
    "orga_level": "Collectors: administrative level",
    "organic_collection_amount": "Organic-fraction amount",
    "organic_waste_ratio": "Organic separation rate",
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
    "waste_ratio": "Biobin separation rate",
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


def _build_map_set_region_scopes():
    scopes = {}
    for page in MAP_PAGES:
        map_set = page["selector_set"]
        if not map_set or map_set in scopes:
            continue
        scopes[map_set] = {
            "country": page["country"],
            "nuts_prefix": page.get("nuts_prefix", ""),
            "nuts_level": str(page.get("nuts_level", "") or ""),
        }
    return scopes


MAP_SET_REGION_SCOPES = _build_map_set_region_scopes()

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
    "participation_policy": 710,
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

MAP_SELECTION_EXACT_THEME_LABELS = {
    "collection_system": "Primary collection system",
    "biowaste_collection_system": "Biowaste collection system",
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
    "participation_policy": "biowaste",
    "food_waste_category": "biowaste",
    "paper_bags": "biowaste",
    "plastic_bags": "biowaste",
    "collection_support": "biowaste",
}

TOPIC_COLOR_CLASSES = {
    "orga_level": "atlas-topic-admin",
    "collection_orga_level": "atlas-topic-admin",
    "population_density": "atlas-topic-admin",
    "collection_system": "atlas-topic-system",
    "collection_system_count": "atlas-topic-system",
    "connection_rate": "atlas-topic-system",
    "participation_policy": "atlas-topic-coverage",
    "food_waste_category": "atlas-topic-material",
    "paper_bags": "atlas-topic-material",
    "plastic_bags": "atlas-topic-material",
    "collection_support": "atlas-topic-material",
    "min_bin_size": "atlas-topic-bin",
    "required_bin_capacity": "atlas-topic-bin",
    "frequency": "atlas-topic-schedule",
    "collection_count": "atlas-topic-count",
    "collection_count_ratio": "atlas-topic-count",
    "collection_point_count": "atlas-topic-count",
    "collection_point_count_ratio": "atlas-topic-count",
    "fee_system": "atlas-topic-fee",
    "collection_amount": "atlas-topic-amount-bio",
    "waste_ratio": "atlas-topic-amount-ratio",
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
    if theme in MAP_SELECTION_EXACT_THEME_LABELS:
        return MAP_SELECTION_EXACT_THEME_LABELS[theme]
    theme_group = _selection_theme_group(theme)
    return MAP_SELECTION_THEME_LABELS.get(theme_group, theme_selection["label"])


def _topic_color_class(theme):
    theme_group = _selection_theme_group(theme)
    if theme_group == "collection_amount":
        waste_category = _selection_waste_category(theme)
        if waste_category == "residual":
            return "atlas-topic-amount-residual"
        if waste_category == "organic":
            return "atlas-topic-amount-organic"
    return TOPIC_COLOR_CLASSES.get(theme_group, "atlas-topic-coverage")


def _theme_sort_key(theme_item):
    theme, theme_selection = theme_item
    return (
        MAP_SELECTION_THEME_ORDER.get(theme, 1000),
        theme_selection["label"],
    )


def _selected_waste_category(selected_map_set, selected_theme, themes_by_map_set):
    selected_category = _selection_waste_category(selected_theme)
    available_categories = {
        theme["waste_category"] for theme in themes_by_map_set.get(selected_map_set, [])
    }
    if selected_category in available_categories:
        return selected_category
    for category in MAP_SELECTION_WASTE_CATEGORIES:
        if category in available_categories:
            return category
    return selected_category


def _theme_context_sort_key(theme_selection):
    return (
        MAP_SELECTION_THEME_ORDER.get(theme_selection["value"], 1000),
        theme_selection["label"],
    )


def _generic_theme_options(reverse_func):
    generic_pages_by_theme = {}
    for page in MAP_PAGES:
        if page["selector_set"] is None:
            generic_pages_by_theme.setdefault(page["theme"], page)

    return [
        {
            "value": theme,
            "theme_group": _selection_theme_group(theme),
            "waste_category": _selection_waste_category(theme),
            "label": _selection_theme_label(
                theme,
                {"label": THEME_LABELS[theme]},
            ),
            "url": reverse_func(page["name"]),
            "change_url": "",
        }
        for theme, page in generic_pages_by_theme.items()
    ]


def _add_generic_theme_fallbacks(themes_by_map_set, reverse_func):
    generic_theme_options = _generic_theme_options(reverse_func)
    for selected_themes in themes_by_map_set.values():
        existing_themes = {theme["value"] for theme in selected_themes}
        selected_themes.extend(
            theme.copy()
            for theme in generic_theme_options
            if theme["value"] not in existing_themes
        )
        selected_themes.sort(key=_theme_context_sort_key)


def _related_map_entry(page, reverse_func, label=None):
    theme = page["theme"]
    map_set = page["selector_set"]
    return {
        "label": label or _selection_theme_label(theme, {"label": THEME_LABELS[theme]}),
        "url": reverse_func(page["name"]),
        "topic_color_class": _topic_color_class(theme),
        "region_label": MAP_SET_LABELS.get(map_set, ""),
    }


def _map_set_scope_params(map_set):
    scope = MAP_SET_REGION_SCOPES.get(map_set)
    if not scope:
        return {}
    params = {"country": scope["country"]}
    if scope["nuts_prefix"]:
        params["nuts_prefix"] = scope["nuts_prefix"]
    if scope["nuts_level"]:
        params["nuts_level"] = scope["nuts_level"]
    return params


def _url_with_map_set_scope(url, map_set):
    params = _map_set_scope_params(map_set)
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


def resolve_map_set(country, nuts_prefix="", nuts_level=""):
    nuts_level = str(nuts_level or "")
    for map_set, scope in MAP_SET_REGION_SCOPES.items():
        if (
            scope["country"] == country
            and scope["nuts_prefix"] == (nuts_prefix or "")
            and scope["nuts_level"] == nuts_level
        ):
            return map_set
    return country


def build_related_maps_context(selected_map_set, selected_theme, reverse_func):
    seen_map_sets = set()
    same_theme_other_regions = []
    for page in MAP_PAGES:
        map_set = page["selector_set"]
        if (
            map_set is None
            or map_set == selected_map_set
            or page["theme"] != selected_theme
            or map_set in seen_map_sets
        ):
            continue
        same_theme_other_regions.append(
            _related_map_entry(
                page,
                reverse_func,
                label=MAP_SET_LABELS[map_set],
            )
        )
        seen_map_sets.add(map_set)

    selection_context = build_map_selection_context(
        reverse_func,
        selected_map_set=selected_map_set,
        selected_theme=selected_theme,
    )
    selected_waste_category = _selection_waste_category(selected_theme)
    selected_theme_group = _selection_theme_group(selected_theme)
    seen_themes = {selected_theme}
    same_region_same_category = []
    for theme in selection_context["map_selection_themes_by_map_set"].get(
        selected_map_set, []
    ):
        theme_value = theme["value"]
        if theme_value in seen_themes or (
            theme["waste_category"] != selected_waste_category
            and theme["theme_group"] != selected_theme_group
        ):
            continue
        same_region_same_category.append(
            {
                "label": theme["label"],
                "url": (
                    _url_with_map_set_scope(theme["url"], selected_map_set)
                    if not theme["change_url"]
                    else theme["url"]
                ),
                "topic_color_class": _topic_color_class(theme_value),
                "region_label": MAP_SET_LABELS.get(selected_map_set, ""),
            }
        )
        seen_themes.add(theme_value)

    return {
        "same_theme_other_regions": same_theme_other_regions,
        "same_region_same_category": same_region_same_category,
    }


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
                "country": MAP_SET_REGION_SCOPES[map_set]["country"],
                "nuts_prefix": MAP_SET_REGION_SCOPES[map_set]["nuts_prefix"],
                "nuts_level": MAP_SET_REGION_SCOPES[map_set]["nuts_level"],
                "selected": map_set == selected_map_set,
            }
        )
    _add_generic_theme_fallbacks(themes_by_map_set, reverse_func)
    return {
        "map_selection_map_sets": map_sets,
        "map_selection_themes_by_map_set": themes_by_map_set,
        "map_selection_waste_categories": MAP_SELECTION_WASTE_CATEGORIES,
        "map_selection_years": MAP_SELECTION_YEARS,
        "selected_map_set": selected_map_set,
        "selected_map_theme": selected_theme,
        "selected_waste_category": _selected_waste_category(
            selected_map_set, selected_theme, themes_by_map_set
        ),
    }
