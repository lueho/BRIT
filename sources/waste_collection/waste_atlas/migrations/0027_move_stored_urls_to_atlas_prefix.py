import json

from django.db import migrations

OLD_API = "/waste_collection/api/waste-atlas/"
NEW_PAGES = "/waste_collection/waste-atlas/map/"
NEW_API = "/waste_collection/waste-atlas/api/"


def _forward(text):
    return text.replace(f"{OLD_API}map/", NEW_PAGES).replace(OLD_API, NEW_API)


def _backward(text):
    return text.replace(NEW_PAGES, f"{OLD_API}map/").replace(NEW_API, OLD_API)


def _rewrite(apps, convert):
    model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    for row in model.objects.all():
        converted = json.loads(convert(json.dumps(row.configuration)))
        if converted != row.configuration:
            row.configuration = converted
            row.save(update_fields=["configuration"])


def move_forward(apps, schema_editor):
    _rewrite(apps, _forward)


def move_backward(apps, schema_editor):
    _rewrite(apps, _backward)


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0026_add_organic_ratio_no_collection"),
    ]

    operations = [migrations.RunPython(move_forward, move_backward)]
