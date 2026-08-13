"""Move the ACPV marker appearance out of the individual map configurations.

Hatching and the group outline are one atlas-wide look now, so a stored
configuration only keeps a value that genuinely deviates from it.  The legacy
``outlineStroke*`` keys are renamed to the ``acpv*`` family the renderer reads,
and a redundant export copy of the hatching legend label is dropped.
"""

from django.db import migrations

LEGACY_OUTLINE_KEYS = {
    "outlineStrokeColor": "acpvOutlineColor",
    "outlineStrokeOpacity": "acpvOutlineOpacity",
    "outlineStrokeWidth": "acpvOutlineWidth",
}
# The values the seeded configurations carried; they are now the atlas defaults.
SEEDED_OUTLINE = {
    "outlineStrokeColor": "#ffffff",
    "outlineStrokeOpacity": 0.95,
    "outlineStrokeWidth": 1.35,
}


def _atlas_defaults(apps):
    settings_model = apps.get_model("waste_atlas", "WasteAtlasRenderingSettings")
    settings = settings_model.objects.first()
    if settings is None:
        return {
            "acpvOutlineColor": "#ffffff",
            "acpvOutlineOpacity": 0.95,
            "acpvOutlineWidth": 1.35,
        }
    return {
        "acpvOutlineColor": settings.acpv_outline_color,
        "acpvOutlineOpacity": settings.acpv_outline_opacity,
        "acpvOutlineWidth": settings.acpv_outline_width,
    }


def centralize(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    defaults = _atlas_defaults(apps)
    for configuration in configuration_model.objects.all():
        stored = dict(configuration.configuration)
        changed = False
        for legacy_key, key in LEGACY_OUTLINE_KEYS.items():
            if legacy_key not in stored:
                continue
            value = stored.pop(legacy_key)
            changed = True
            # Only a genuine deviation stays; the rest follows the atlas.
            if value != defaults[key]:
                stored[key] = value
        if stored.get("exportOverlayPatternLegendLabel") == stored.get(
            "overlayPatternLegendLabel"
        ):
            stored.pop("exportOverlayPatternLegendLabel", None)
            changed = True
        if changed:
            configuration.configuration = stored
            configuration.save(update_fields=["configuration"])


def restore(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    for configuration in configuration_model.objects.all():
        stored = dict(configuration.configuration)
        if "overlayPatternField" not in stored:
            continue
        if "outlineGeoJsonUrl" in stored:
            for legacy_key, key in LEGACY_OUTLINE_KEYS.items():
                stored[legacy_key] = stored.pop(key, SEEDED_OUTLINE[legacy_key])
        if "overlayPatternLegendLabel" in stored:
            stored.setdefault(
                "exportOverlayPatternLegendLabel",
                stored["overlayPatternLegendLabel"],
            )
        configuration.configuration = stored
        configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0012_wasteatlasrenderingsettings_acpv_hatch_color_and_more"),
    ]

    operations = [migrations.RunPython(centralize, restore)]
