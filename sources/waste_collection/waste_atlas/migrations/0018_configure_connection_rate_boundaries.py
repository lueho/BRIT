"""Offer fixed and tie-safe quartile classes for connection rates."""

from django.db import migrations

FULL_CONNECTION_VALUE = "full_connection"
FULL_CONNECTION_LABEL = "100% – full connection"
FULL_CONNECTION_COLOR = "#003f5c"

FIXED_LABELS = {
    "75-99": "75% – <100%",
    "50-74": "50% – <75%",
    "25-49": "25% – <50%",
    "0-24": "0% – <25%",
}

LEGACY_LABELS = {
    "75-100": "100% – 75%",
    "50-74": "74% – 50%",
    "25-49": "49% – 25%",
    "0-24": "24% – 0%",
}


def configure_connection_rate_boundaries(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)

    categories = []
    for original in configuration["categories"]:
        category = dict(original)
        if category.get("value") == "75-100":
            categories.append(
                {
                    "value": FULL_CONNECTION_VALUE,
                    "label": FULL_CONNECTION_LABEL,
                    "color": FULL_CONNECTION_COLOR,
                }
            )
            category["value"] = "75-99"
        if category.get("value") in FIXED_LABELS:
            category["label"] = FIXED_LABELS[category["value"]]
        categories.append(category)

    special_cases = [
        dict(special_case)
        for special_case in configuration.get("quartileSpecialCases", [])
        if special_case.get("classValue") != FULL_CONNECTION_VALUE
    ]
    special_cases.append(
        {
            "field": "connection_rate",
            "equals": 1,
            "classValue": FULL_CONNECTION_VALUE,
            "label": FULL_CONNECTION_LABEL,
            "color": FULL_CONNECTION_COLOR,
        }
    )

    configuration["categories"] = categories
    configuration["quartileSpecialCases"] = special_cases
    configuration["enableQuartiles"] = True
    configuration["quartileDefaultEnabled"] = False
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


def restore_connection_rate_boundaries(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)

    categories = []
    for original in configuration["categories"]:
        category = dict(original)
        if category.get("value") == FULL_CONNECTION_VALUE:
            continue
        if category.get("value") == "75-99":
            category["value"] = "75-100"
        if category.get("value") in LEGACY_LABELS:
            category["label"] = LEGACY_LABELS[category["value"]]
        categories.append(category)

    special_cases = [
        dict(special_case)
        for special_case in configuration.get("quartileSpecialCases", [])
        if special_case.get("classValue") != FULL_CONNECTION_VALUE
    ]

    configuration["categories"] = categories
    if special_cases:
        configuration["quartileSpecialCases"] = special_cases
    else:
        configuration.pop("quartileSpecialCases", None)
    configuration["enableQuartiles"] = False
    configuration.pop("quartileDefaultEnabled", None)
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0017_disable_connection_rate_quartiles"),
    ]

    operations = [
        migrations.RunPython(
            configure_connection_rate_boundaries,
            restore_connection_rate_boundaries,
        )
    ]
