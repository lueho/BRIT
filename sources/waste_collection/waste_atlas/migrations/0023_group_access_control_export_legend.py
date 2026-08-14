"""Group the access-control export legend by collection-mode relationship."""

from django.db import migrations

LEGEND_ORDER = [
    "Bring point: yes",
    "Bring point: no",
    "Door-to-door: yes",
    "Door-to-door: no",
    "Bring point: yes | Door-to-door: yes",
    "Bring point: no | Door-to-door: yes",
    "Bring point: yes | Door-to-door: no",
    "Bring point: no | Door-to-door: no",
    "No separate biowaste collection",
]

CATEGORY_COLORS = {
    "Bring point: yes | Door-to-door: yes": "#542788",
    "Bring point: no | Door-to-door: yes": "#998ec3",
    "Bring point: yes | Door-to-door: no": "#b2182b",
    "Bring point: no | Door-to-door: no": "#ef8a62",
}

ORIGINAL_CATEGORY_COLORS = {
    "Bring point: yes | Door-to-door: yes": "#542788",
    "Bring point: no | Door-to-door: no": "#c2a5cf",
    "Bring point: yes | Door-to-door: no": "#b2182b",
    "Bring point: no | Door-to-door: yes": "#ef8a62",
}


def update_access_control_legend(apps, schema_editor, *, grouped):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    configuration = configuration_model.objects.filter(key="access_control").first()
    if configuration is None:
        return

    stored = dict(configuration.configuration)
    colors = CATEGORY_COLORS if grouped else ORIGINAL_CATEGORY_COLORS
    for category in stored.get("categories", []):
        color = colors.get(category.get("value"))
        if color:
            category["color"] = color

    if grouped:
        stored["legendCategoryOrder"] = LEGEND_ORDER
        stored["exportLegendColumns"] = 3
        stored["exportLegendItemFlow"] = "column"
        stored["legendColumnBreakBefore"] = [
            "Bring point: yes | Door-to-door: yes",
            "No separate biowaste collection",
        ]
    else:
        for key in (
            "legendCategoryOrder",
            "exportLegendColumns",
            "exportLegendItemFlow",
            "legendColumnBreakBefore",
        ):
            stored.pop(key, None)

    configuration.configuration = stored
    configuration.save(update_fields=["configuration"])


def group_legend(apps, schema_editor):
    update_access_control_legend(apps, schema_editor, grouped=True)


def restore_legend(apps, schema_editor):
    update_access_control_legend(apps, schema_editor, grouped=False)


class Migration(migrations.Migration):
    dependencies = [("waste_atlas", "0022_add_access_control_legend_note")]

    operations = [migrations.RunPython(group_legend, restore_legend)]
