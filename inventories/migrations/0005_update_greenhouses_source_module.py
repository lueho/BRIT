from django.db import migrations

OLD_MODULE = "flexibi_nantes"
NEW_MODULE = "sources.greenhouses.inventory.algorithms"


def forwards(apps, schema_editor):
    InventoryAlgorithm = apps.get_model("inventories", "InventoryAlgorithm")
    InventoryAlgorithm.objects.filter(source_module=OLD_MODULE).update(
        source_module=NEW_MODULE
    )


def backwards(apps, schema_editor):
    InventoryAlgorithm = apps.get_model("inventories", "InventoryAlgorithm")
    InventoryAlgorithm.objects.filter(source_module=NEW_MODULE).update(
        source_module=OLD_MODULE
    )


class Migration(migrations.Migration):
    dependencies = [
        ("inventories", "0004_alter_scenario_publication_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
