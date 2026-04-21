from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inventories", "0005_update_greenhouses_source_module"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="scenariostatus",
            options={"verbose_name_plural": "scenario statuses"},
        ),
    ]
