"""Use the common German 2024 bin sizes as fixed legend categories."""

from django.db import migrations

BIOWASTE_CATEGORIES = [
    {"value": "under_40", "label": "< 40", "color": "#ffffe5"},
    {"value": "exactly_40", "label": "40", "color": "#f7fcb9"},
    {
        "value": "between_40_and_60",
        "label": "41 – 59",
        "color": "#d9f0a3",
    },
    {"value": "exactly_60", "label": "60", "color": "#addd8e"},
    {
        "value": "between_60_and_80",
        "label": "61 – 79",
        "color": "#78c679",
    },
    {"value": "exactly_80", "label": "80", "color": "#41ab5d"},
    {
        "value": "between_80_and_120",
        "label": "81 – 119",
        "color": "#238443",
    },
    {"value": "exactly_120", "label": "120", "color": "#006837"},
    {"value": "over_120", "label": "> 120", "color": "#004529"},
]

RESIDUAL_CATEGORIES = [
    {"value": "under_40", "label": "< 40", "color": "#fff5f0"},
    {"value": "exactly_40", "label": "40", "color": "#fee0d2"},
    {
        "value": "between_40_and_60",
        "label": "41 – 59",
        "color": "#fcbba1",
    },
    {"value": "exactly_60", "label": "60", "color": "#fc9272"},
    {
        "value": "between_60_and_80",
        "label": "61 – 79",
        "color": "#fb6a4a",
    },
    {"value": "exactly_80", "label": "80", "color": "#ef3b2c"},
    {
        "value": "between_80_and_120",
        "label": "81 – 119",
        "color": "#cb181d",
    },
    {"value": "exactly_120", "label": "120", "color": "#a50f15"},
    {"value": "over_120", "label": "> 120", "color": "#67000d"},
]

OLD_BIOWASTE_CATEGORIES = [
    {"value": "xs", "label": "≤ 26.5", "color": "#d9f0d3"},
    {"value": "small", "label": "27 – 60", "color": "#a6d96a"},
    {"value": "medium", "label": "61 – 120", "color": "#1a9850"},
    {"value": "large", "label": "121 – 140", "color": "#006837"},
]

OLD_RESIDUAL_CATEGORIES = [
    {"value": "xs", "label": "≤ 30", "color": "#fde0dd"},
    {"value": "small", "label": "31 – 60", "color": "#fc9272"},
    {"value": "medium", "label": "61 – 120", "color": "#de2d26"},
    {"value": "large", "label": "121 – 240", "color": "#67000d"},
]


def _replace_numeric_categories(configuration, numeric_categories):
    stored = dict(configuration.configuration)
    special_categories = [
        dict(category)
        for category in stored.get("categories", [])
        if category.get("value") == "no_door_to_door"
    ]
    stored["categories"] = [
        *[dict(category) for category in numeric_categories],
        *special_categories,
    ]
    stored["legendCategoryOrder"] = [
        category["value"] for category in stored["categories"]
    ]
    stored["enableQuartiles"] = False
    configuration.configuration = stored
    configuration.save(update_fields=["configuration"])


def reclassify(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    categories_by_key = {
        "biowaste_min_bin_size": BIOWASTE_CATEGORIES,
        "residual_min_bin_size": RESIDUAL_CATEGORIES,
    }
    for key, categories in categories_by_key.items():
        configuration = configuration_model.objects.filter(key=key).first()
        if configuration is not None:
            _replace_numeric_categories(configuration, categories)


def restore(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    categories_by_key = {
        "biowaste_min_bin_size": OLD_BIOWASTE_CATEGORIES,
        "residual_min_bin_size": OLD_RESIDUAL_CATEGORIES,
    }
    for key, categories in categories_by_key.items():
        configuration = configuration_model.objects.filter(key=key).first()
        if configuration is None:
            continue
        _replace_numeric_categories(configuration, categories)
        stored = dict(configuration.configuration)
        stored.pop("enableQuartiles", None)
        configuration.configuration = stored
        configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0019_include_all_connection_rates_in_quartiles"),
    ]

    operations = [migrations.RunPython(reclassify, restore)]
