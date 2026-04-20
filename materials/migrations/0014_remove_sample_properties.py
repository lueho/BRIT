from django.db import migrations


def normalize_material_property_value_samples(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Sample = apps.get_model("materials", "Sample")
    MaterialPropertyValue = apps.get_model("materials", "MaterialPropertyValue")
    property_link_model = Sample._meta.get_field("properties").remote_field.through
    source_link_model = MaterialPropertyValue._meta.get_field(
        "sources"
    ).remote_field.through

    linked_sample_ids_by_value = {}
    for value_id, sample_id in (
        property_link_model.objects.using(db_alias)
        .order_by("materialpropertyvalue_id", "sample_id")
        .values_list("materialpropertyvalue_id", "sample_id")
    ):
        linked_sample_ids_by_value.setdefault(value_id, []).append(sample_id)

    source_ids_by_value = {}
    for value_id, source_id in (
        source_link_model.objects.using(db_alias)
        .order_by("materialpropertyvalue_id", "source_id")
        .values_list("materialpropertyvalue_id", "source_id")
    ):
        source_ids_by_value.setdefault(value_id, []).append(source_id)

    cloneable_fields = [
        field
        for field in MaterialPropertyValue._meta.concrete_fields
        if not field.primary_key and field.name != "sample"
    ]
    auto_managed_field_names = [
        field.attname
        for field in cloneable_fields
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    ]

    property_value_ids = list(linked_sample_ids_by_value)
    if not property_value_ids:
        return

    for property_value in (
        MaterialPropertyValue.objects.using(db_alias)
        .filter(pk__in=property_value_ids)
        .order_by("pk")
        .iterator()
    ):
        linked_sample_ids = sorted(
            set(linked_sample_ids_by_value.get(property_value.pk, []))
        )
        if property_value.sample_id is None:
            if not linked_sample_ids:
                continue
            MaterialPropertyValue.objects.using(db_alias).filter(
                pk=property_value.pk,
                sample__isnull=True,
            ).update(sample_id=linked_sample_ids[0])
            extra_sample_ids = linked_sample_ids[1:]
        else:
            extra_sample_ids = [
                sample_id
                for sample_id in linked_sample_ids
                if sample_id != property_value.sample_id
            ]

        if not extra_sample_ids:
            continue

        field_values = {
            field.attname: getattr(property_value, field.attname)
            for field in cloneable_fields
        }
        source_ids = source_ids_by_value.get(property_value.pk, [])

        for sample_id in extra_sample_ids:
            duplicate = MaterialPropertyValue.objects.using(db_alias).create(
                sample_id=sample_id,
                **field_values,
            )
            if auto_managed_field_names:
                MaterialPropertyValue.objects.using(db_alias).filter(
                    pk=duplicate.pk
                ).update(**{
                    field_name: field_values[field_name]
                    for field_name in auto_managed_field_names
                })
            if source_ids:
                source_link_model.objects.using(db_alias).bulk_create([
                    source_link_model(
                        materialpropertyvalue_id=duplicate.pk,
                        source_id=source_id,
                    )
                    for source_id in source_ids
                ])


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0013_materialpropertyvalue_sample"),
    ]

    operations = [
        migrations.RunPython(
            normalize_material_property_value_samples,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="sample",
            name="properties",
        ),
    ]
