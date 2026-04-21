from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0013_alter_geodatasetcolumnpolicy_id_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="geodatasetcolumnpolicy",
            options={
                "ordering": ["column_name"],
                "verbose_name_plural": "geo dataset column policies",
            },
        ),
        migrations.AlterModelOptions(
            name="regionproperty",
            options={"verbose_name_plural": "region properties"},
        ),
    ]
