from django.db import migrations

GREENHOUSE_MODEL_NAMES = [
    "casestudybaseobjects",
    "culture",
    "greenhouse",
    "greenhousegrowthcycle",
    "growthshare",
    "growthtimestepset",
    "nantesgreenhouses",
]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="flexibi_nantes", model__in=GREENHOUSE_MODEL_NAMES
    ).update(app_label="greenhouses")


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="greenhouses", model__in=GREENHOUSE_MODEL_NAMES
    ).update(app_label="flexibi_nantes")


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("greenhouses", "0001_move_legacy_models"),
        ("flexibi_nantes", "0005_move_models_to_sources"),
    ]

    operations = [
        migrations.RunPython(update_content_types, reverse_update_content_types)
    ]
