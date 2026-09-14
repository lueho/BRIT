from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("waste_collection", "0006_rename_connection_type_to_participation_policy"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="collectioncountoptions",
            options={
                "verbose_name": "collection count options",
                "verbose_name_plural": "collection count options",
            },
        ),
    ]
