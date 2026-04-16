from django.db import migrations, models
from django.db.models import Count, Min


def backfill_material_property_value_sample(apps, schema_editor):
    Sample = apps.get_model("materials", "Sample")
    MaterialPropertyValue = apps.get_model("materials", "MaterialPropertyValue")
    through_model = Sample._meta.get_field("properties").remote_field.through

    unique_links = through_model.objects.values("materialpropertyvalue_id").annotate(
        sample_count=Count("sample_id"),
        linked_sample_id=Min("sample_id"),
    )
    unique_links = unique_links.filter(sample_count=1)

    for link in unique_links.iterator():
        MaterialPropertyValue.objects.filter(
            pk=link["materialpropertyvalue_id"],
            sample__isnull=True,
        ).update(sample_id=link["linked_sample_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0012_alter_analyticalmethod_sources_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sample",
            name="properties",
            field=models.ManyToManyField(
                related_name="sample_set",
                related_query_name="legacy_sample",
                to="materials.materialpropertyvalue",
            ),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="sample",
            field=models.ForeignKey(
                blank=True,
                help_text="The sample this measurement belongs to.",
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="property_values",
                to="materials.sample",
            ),
        ),
        migrations.RunPython(
            backfill_material_property_value_sample,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
