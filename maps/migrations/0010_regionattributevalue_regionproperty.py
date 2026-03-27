import django.db.models.deletion
from django.db import migrations, models


def copy_region_attribute_value_properties(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    RegionAttributeValue = apps.get_model("maps", "RegionAttributeValue")

    for value in RegionAttributeValue.objects.using(db_alias).all().iterator():
        value.property_id = value.attribute_id
        value.save(update_fields=["property"])


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0009_regionproperty"),
    ]

    operations = [
        migrations.AddField(
            model_name="regionattributevalue",
            name="property",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="maps.regionproperty",
            ),
        ),
        migrations.RunPython(
            copy_region_attribute_value_properties,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="regionattributevalue",
            name="attribute",
        ),
        migrations.AlterField(
            model_name="regionattributevalue",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="maps.regionproperty",
            ),
        ),
    ]
