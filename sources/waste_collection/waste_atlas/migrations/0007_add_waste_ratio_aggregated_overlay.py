from django.db import migrations

OVERLAY_CONFIGURATION = {
    "overlayPatternField": "uses_aggregated_amount",
    "overlayPatternLegendLabel": "Hatched = includes aggregated value",
    "exportOverlayPatternLegendLabel": "Hatched = includes aggregated value",
}


def add_waste_ratio_aggregated_overlay(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration = configuration_model.objects.get(key="waste_ratio")
    configuration.configuration = {
        **configuration.configuration,
        **OVERLAY_CONFIGURATION,
    }
    configuration.save(update_fields=["configuration"])


def remove_waste_ratio_aggregated_overlay(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration = configuration_model.objects.get(key="waste_ratio")
    configuration.configuration = {
        key: value
        for key, value in configuration.configuration.items()
        if key not in OVERLAY_CONFIGURATION
    }
    configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0006_add_residual_collection_amount_acpv_overlay"),
    ]

    operations = [
        migrations.RunPython(
            add_waste_ratio_aggregated_overlay,
            remove_waste_ratio_aggregated_overlay,
        ),
    ]
