from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0014_remove_sample_properties"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="materialcategory",
            options={
                "ordering": ["name", "id"],
                "verbose_name_plural": "material categories",
            },
        ),
        migrations.AlterModelOptions(
            name="materialproperty",
            options={"verbose_name_plural": "material properties"},
        ),
        migrations.AlterModelOptions(
            name="sampleseries",
            options={
                "ordering": ["name", "id"],
                "verbose_name_plural": "sample series",
            },
        ),
    ]
