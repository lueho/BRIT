"""Calculate connection-rate quartiles from every numeric value."""

from django.db import migrations

FULL_CONNECTION_VALUE = "full_connection"
FULL_CONNECTION_SPECIAL_CASE = {
    "field": "connection_rate",
    "equals": 1,
    "classValue": FULL_CONNECTION_VALUE,
    "label": "100% – full connection",
    "color": "#003f5c",
}


def include_all_connection_rates(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)
    special_cases = [
        dict(special_case)
        for special_case in configuration.get("quartileSpecialCases", [])
        if special_case.get("classValue") != FULL_CONNECTION_VALUE
    ]
    if special_cases:
        configuration["quartileSpecialCases"] = special_cases
    else:
        configuration.pop("quartileSpecialCases", None)
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


def exclude_full_connection_from_quartiles(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)
    special_cases = [
        dict(special_case)
        for special_case in configuration.get("quartileSpecialCases", [])
        if special_case.get("classValue") != FULL_CONNECTION_VALUE
    ]
    special_cases.append(FULL_CONNECTION_SPECIAL_CASE)
    configuration["quartileSpecialCases"] = special_cases
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0018_configure_connection_rate_boundaries"),
    ]

    operations = [
        migrations.RunPython(
            include_all_connection_rates,
            exclude_full_connection_from_quartiles,
        )
    ]
