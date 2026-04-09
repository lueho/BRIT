from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0010_materialpropertyvalue_basis_component"),
    ]

    operations = [
        migrations.AlterField(
            model_name="componentmeasurement",
            name="standard_deviation",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="materialpropertyvalue",
            name="standard_deviation",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                max_digits=20,
                null=True,
            ),
        ),
    ]
