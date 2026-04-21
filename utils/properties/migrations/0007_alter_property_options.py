from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0006_merge_20260217_0951"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="property",
            options={"verbose_name_plural": "properties"},
        ),
    ]
