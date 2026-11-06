import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "waste_collection",
            "0012_alter_collection_options",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="collectionpropertyvalue",
            name="derived_from",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                help_text=(
                    "The raw source value this generated projection is derived from. "
                    "Server-controlled; set only by the derivation pipeline."
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="generated_values",
                to="waste_collection.collectionpropertyvalue",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="collectionpropertyvalue",
            name="soilcom_unique_derived_cpv_per_key",
        ),
        migrations.RemoveConstraint(
            model_name="collectionpropertyvalue",
            name="soilcom_unique_derived_cpv_per_key_null_year",
        ),
        migrations.AddConstraint(
            model_name="collectionpropertyvalue",
            constraint=models.UniqueConstraint(
                fields=["derived_from"],
                condition=models.Q(is_derived=True, derived_from__isnull=False),
                name="wc_unique_generated_cpv_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectionpropertyvalue",
            constraint=models.CheckConstraint(
                condition=models.Q(is_derived=True)
                | models.Q(derived_from__isnull=True),
                name="soilcom_cpv_raw_without_source_pointer",
            ),
        ),
    ]
