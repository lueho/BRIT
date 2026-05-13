from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0014_alter_geodatasetcolumnpolicy_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="geodatasetcolumnpolicy",
            name="is_popup",
            field=models.BooleanField(default=False),
        ),
    ]
