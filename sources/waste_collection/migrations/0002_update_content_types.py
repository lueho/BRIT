from django.db import migrations


WASTE_COLLECTION_MODEL_NAMES = [
    "aggregatedcollectionpropertyvalue",
    "collection",
    "collectioncatchment",
    "collectioncountoptions",
    "collectionfrequency",
    "collectionpropertyvalue",
    "collectionseason",
    "collectionsystem",
    "collector",
    "feesystem",
    "sortingmethod",
    "wastecategory",
    "wastecomponent",
    "wasteflyer",
]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="soilcom", model__in=WASTE_COLLECTION_MODEL_NAMES
    ).update(app_label="waste_collection")


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="waste_collection", model__in=WASTE_COLLECTION_MODEL_NAMES
    ).update(app_label="soilcom")


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("waste_collection", "0001_move_legacy_models"),
        ("soilcom", "0013_move_models_to_sources"),
    ]

    operations = [migrations.RunPython(update_content_types, reverse_update_content_types)]
