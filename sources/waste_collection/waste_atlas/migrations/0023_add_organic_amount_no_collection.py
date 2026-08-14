from django.db import migrations

NO_COLLECTION_VALUE = "no_collection"
NO_COLLECTION_LABEL = "No separate collection"
DEFAULT_NO_COLLECTION_COLOR = "#fff696"


def add_organic_amount_no_collection(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    settings_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasRenderingSettings",
    )
    no_collection_color = (
        settings_model.objects.filter(pk=1)
        .values_list("no_collection_color", flat=True)
        .first()
        or DEFAULT_NO_COLLECTION_COLOR
    )

    stored = configuration_model.objects.get(key="organic_collection_amount")
    configuration = dict(stored.configuration)
    categories = list(configuration.get("categories", []))
    special_cases = list(configuration.get("quartileSpecialCases", []))

    if not any(entry.get("value") == NO_COLLECTION_VALUE for entry in categories):
        categories.append(
            {
                "value": NO_COLLECTION_VALUE,
                "label": NO_COLLECTION_LABEL,
                "color": no_collection_color,
            }
        )
    if not any(entry.get("field") == "no_collection" for entry in special_cases):
        special_cases.append(
            {
                "field": "no_collection",
                "classValue": NO_COLLECTION_VALUE,
                "label": NO_COLLECTION_LABEL,
                "color": no_collection_color,
            }
        )

    configuration["categories"] = categories
    configuration["quartileSpecialCases"] = special_cases
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


def remove_organic_amount_no_collection(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    stored = configuration_model.objects.get(key="organic_collection_amount")
    configuration = dict(stored.configuration)
    configuration["categories"] = [
        entry
        for entry in configuration.get("categories", [])
        if entry.get("value") != NO_COLLECTION_VALUE
    ]
    configuration["quartileSpecialCases"] = [
        entry
        for entry in configuration.get("quartileSpecialCases", [])
        if entry.get("field") != "no_collection"
    ]
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0022_add_access_control_legend_note"),
    ]

    operations = [
        migrations.RunPython(
            add_organic_amount_no_collection,
            remove_organic_amount_no_collection,
        ),
    ]
