from django.db import migrations


HAMBURG_MODEL_NAMES = ["hamburgroadsidetrees", "hamburggreenareas"]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="flexibi_hamburg", model__in=HAMBURG_MODEL_NAMES
    ).update(app_label="roadside_trees")


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="roadside_trees", model__in=HAMBURG_MODEL_NAMES
    ).update(app_label="flexibi_hamburg")


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("roadside_trees", "0001_move_legacy_models"),
        ("flexibi_hamburg", "0003_move_models_to_sources"),
    ]

    operations = [migrations.RunPython(update_content_types, reverse_update_content_types)]
