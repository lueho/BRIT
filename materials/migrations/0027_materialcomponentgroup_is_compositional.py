from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0026_basematerial_is_aggregate"),
    ]

    operations = [
        migrations.AddField(
            model_name="materialcomponentgroup",
            name="is_compositional",
            field=models.BooleanField(default=True),
        ),
    ]
