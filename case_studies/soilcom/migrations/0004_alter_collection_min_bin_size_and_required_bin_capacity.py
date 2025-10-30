from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("soilcom", "0003_alter_aggregatedcollectionpropertyvalue_publication_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collection",
            name="min_bin_size",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text=(
                    "Smallest physical bin size that the collector provides for this collection. Exceprions may apply (e.g. for home composters)"
                ),
                max_digits=8,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Smallest available bin size (L)",
            ),
        ),
        migrations.AlterField(
            model_name="collection",
            name="required_bin_capacity",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text="Minimum total bin capacity that must be supplied per reference unit (see field below).",
                max_digits=8,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Required bin capacity per unit (L)",
            ),
        ),
    ]
