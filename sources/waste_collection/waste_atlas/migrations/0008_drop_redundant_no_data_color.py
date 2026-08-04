from django.db import migrations

DEFAULT_NO_DATA_COLOR = "#e0e0e0"


def drop_redundant_no_data_color(apps, schema_editor):
    model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    for configuration in model.objects.all():
        if configuration.configuration.get("noDataColor") != DEFAULT_NO_DATA_COLOR:
            continue
        configuration.configuration.pop("noDataColor")
        configuration.save(update_fields=["configuration"])


def restore_no_data_color(apps, schema_editor):
    model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    for configuration in model.objects.all():
        if "noDataColor" in configuration.configuration:
            continue
        configuration.configuration["noDataColor"] = DEFAULT_NO_DATA_COLOR
        configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0007_seed_rendering_settings"),
        ("waste_atlas", "0007_add_waste_ratio_aggregated_overlay"),
    ]

    operations = [
        migrations.RunPython(drop_redundant_no_data_color, restore_no_data_color),
    ]
