from django.db import migrations

URBAN_GREEN_SPACE_MODEL_NAMES = ["hamburggreenareas"]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="roadside_trees", model__in=URBAN_GREEN_SPACE_MODEL_NAMES
    ).update(app_label="urban_green_spaces")


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="urban_green_spaces", model__in=URBAN_GREEN_SPACE_MODEL_NAMES
    ).update(app_label="roadside_trees")


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("urban_green_spaces", "0001_move_green_areas_from_roadside_trees"),
        ("roadside_trees", "0003_remove_green_areas_model"),
    ]

    operations = [
        migrations.RunPython(update_content_types, reverse_update_content_types)
    ]
