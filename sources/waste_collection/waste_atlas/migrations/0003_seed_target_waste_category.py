from django.db import migrations

TARGET_WASTE_CATEGORY_CONFIGURATION = {
    "title": "Target waste category",
    "dataUrl": "/waste_collection/api/waste-atlas/target-waste-category/",
    "dataField": "target_waste_category",
    "categories": [
        {
            "value": "Biowaste",
            "label": "Biowaste",
            "color": "#94cf7c",
        },
        {
            "value": "Food waste",
            "label": "Food waste",
            "color": "#debf6a",
        },
        {
            "value": "No separate collection",
            "label": "No separate collection",
            "color": "#d7d7d7",
        },
    ],
    "noDataColor": "#e0e0e0",
    "noDataLabel": "No data",
    "legendTitle": "Target waste category",
    "fileBase": "south_tyrol_target_waste_category",
}


def seed_target_waste_category(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration_model.objects.update_or_create(
        key="target_waste_category",
        defaults={"configuration": TARGET_WASTE_CATEGORY_CONFIGURATION},
    )


def remove_target_waste_category(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration_model.objects.filter(key="target_waste_category").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0002_seed_map_configurations"),
    ]

    operations = [
        migrations.RunPython(
            seed_target_waste_category,
            remove_target_waste_category,
        ),
    ]
