from django.db import migrations, models
from django.db.models import Count, Min


def merge_duplicate_layer_fields(apps, using):
    """Collapse LayerFields sharing (field_name, data_type) into the oldest row."""
    LayerField = apps.get_model("layer_manager", "LayerField")
    Layer = apps.get_model("layer_manager", "Layer")
    LayerLayerField = Layer.layer_fields.through

    duplicate_groups = (
        LayerField.objects.using(using)
        .order_by()
        .values("field_name", "data_type")
        .annotate(keep_id=Min("id"), row_count=Count("id"))
        .filter(row_count__gt=1)
    )
    for group in duplicate_groups:
        keep_id = group["keep_id"]
        duplicate_ids = list(
            LayerField.objects.using(using)
            .filter(field_name=group["field_name"], data_type=group["data_type"])
            .exclude(id=keep_id)
            .values_list("id", flat=True)
        )
        duplicate_layer_ids = set(
            LayerLayerField.objects.using(using)
            .filter(layerfield_id__in=duplicate_ids)
            .values_list("layer_id", flat=True)
        )
        linked_layer_ids = set(
            LayerLayerField.objects.using(using)
            .filter(layerfield_id=keep_id)
            .values_list("layer_id", flat=True)
        )
        LayerLayerField.objects.using(using).bulk_create(
            LayerLayerField(layer_id=layer_id, layerfield_id=keep_id)
            for layer_id in duplicate_layer_ids - linked_layer_ids
        )
        LayerField.objects.using(using).filter(id__in=duplicate_ids).delete()


def lock_and_merge_duplicate_layer_fields(apps, schema_editor):
    """
    Block concurrent LayerField inserts until the unique constraint exists, then
    merge duplicates. Deferred FK triggers are fired immediately so the table can
    be altered in the same transaction.
    """
    LayerField = apps.get_model("layer_manager", "LayerField")
    table = schema_editor.quote_name(LayerField._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
    merge_duplicate_layer_fields(apps, schema_editor.connection.alias)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("layer_manager", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            lock_and_merge_duplicate_layer_fields, migrations.RunPython.noop
        ),
        migrations.AddConstraint(
            model_name="layerfield",
            constraint=models.UniqueConstraint(
                fields=("field_name", "data_type"),
                name="unique_layer_field_name_data_type",
            ),
        ),
    ]
