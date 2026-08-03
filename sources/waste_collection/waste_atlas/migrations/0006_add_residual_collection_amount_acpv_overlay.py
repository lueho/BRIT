from django.db import migrations

OVERLAY_CONFIGURATION = {
    "outlineGeoJsonUrl": (
        "/waste_collection/api/waste-atlas/residual-collection-amount/"
        "acpv-outline-geojson/"
    ),
    "outlineStrokeColor": "#ffffff",
    "outlineStrokeOpacity": 0.95,
    "outlineStrokeWidth": 1.35,
    "overlayPatternField": "_has_acpv_overlay",
    "overlayPatternLegendLabel": "Hatched = aggregated value",
    "exportOverlayPatternLegendLabel": "Hatched = aggregated value",
}


def add_residual_collection_amount_acpv_overlay(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration = configuration_model.objects.get(key="residual_collection_amount")
    configuration.configuration = {
        **configuration.configuration,
        **OVERLAY_CONFIGURATION,
    }
    configuration.save(update_fields=["configuration"])


def remove_residual_collection_amount_acpv_overlay(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration = configuration_model.objects.get(key="residual_collection_amount")
    configuration.configuration = {
        key: value
        for key, value in configuration.configuration.items()
        if key not in OVERLAY_CONFIGURATION
    }
    configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0005_merge_20260730_1555"),
    ]

    operations = [
        migrations.RunPython(
            add_residual_collection_amount_acpv_overlay,
            remove_residual_collection_amount_acpv_overlay,
        ),
    ]
