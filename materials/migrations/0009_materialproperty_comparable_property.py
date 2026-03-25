import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0008_basematerial_comparable_component"),
    ]

    operations = [
        migrations.AddField(
            model_name="materialproperty",
            name="comparable_property",
            field=models.ForeignKey(
                blank=True,
                help_text="Canonical property this raw term should be compared as.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="comparable_variants",
                to="materials.materialproperty",
            ),
        ),
    ]
