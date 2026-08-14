"""Compact the Catalonia access-control legend and document its abbreviations."""

from django.db import migrations

COMPACT_LABELS = {
    "Bring point: yes": "BP: yes",
    "Bring point: no": "BP: no",
    "Door-to-door: yes": "DtD: yes",
    "Door-to-door: no": "DtD: no",
    "Bring point: yes | Door-to-door: yes": "DtD: yes | BP: yes",
    "Bring point: no | Door-to-door: no": "DtD: no | BP: no",
    "Bring point: yes | Door-to-door: no": "DtD: no | BP: yes",
    "Bring point: no | Door-to-door: yes": "DtD: yes | BP: no",
}

ORIGINAL_LABELS = {value: key for key, value in COMPACT_LABELS.items()}


def update_access_control_legend(apps, schema_editor, *, compact):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    configuration = configuration_model.objects.filter(key="access_control").first()
    if configuration is None:
        return

    stored = dict(configuration.configuration)
    labels = COMPACT_LABELS if compact else ORIGINAL_LABELS
    for category in stored.get("categories", []):
        label = category.get("label")
        if label in labels:
            category["label"] = labels[label]

    if compact:
        stored["legendTitle"] = "Collection mode + Access/use control"
        stored["legendNote"] = "DtD = Door to door · BP = Bring point"
        stored["legendWidth"] = 400
    else:
        stored["legendTitle"] = "Access control"
        stored.pop("legendNote", None)
        stored.pop("legendWidth", None)

    configuration.configuration = stored
    configuration.save(update_fields=["configuration"])


def compact_legend(apps, schema_editor):
    update_access_control_legend(apps, schema_editor, compact=True)


def restore_legend(apps, schema_editor):
    update_access_control_legend(apps, schema_editor, compact=False)


class Migration(migrations.Migration):
    dependencies = [("waste_atlas", "0021_hide_absent_min_bin_size_categories")]

    operations = [migrations.RunPython(compact_legend, restore_legend)]
