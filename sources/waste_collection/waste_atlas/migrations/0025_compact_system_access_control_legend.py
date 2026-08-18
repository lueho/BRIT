"""Compact the system access-control legend and reserve grey for no data."""

from django.db import migrations

CATEGORY_UPDATES = {
    "Bring point + access control": {"label": "BP + control"},
    "Bring point + no access control": {"label": "BP + no control"},
    "PAP + use control": {
        "value": "Door to door + control",
        "label": "DtD + control",
    },
    "PAP + no use control": {
        "value": "Door to door + no control",
        "label": "DtD + no control",
    },
    "Other combination": {"color": "#fdae61"},
}


def update_system_access_control_legend(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    configuration = configuration_model.objects.filter(
        key="system_access_control"
    ).first()
    if configuration is None:
        return

    stored = dict(configuration.configuration)
    for category in stored.get("categories", []):
        category.update(CATEGORY_UPDATES.get(category.get("value"), {}))
    stored["legendTitle"] = "Collection mode + Access/use control"
    stored["legendNote"] = "DtD = Door to door · BP = Bring point"
    configuration.configuration = stored
    configuration.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [("waste_atlas", "0024_group_access_control_export_legend")]

    operations = [migrations.RunPython(update_system_access_control_legend)]
