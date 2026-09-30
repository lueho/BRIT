from django.db import migrations
from django.db.models import Count, Min


def merge_duplicate_layer_fields(apps, schema_editor):
    """Collapse LayerFields sharing (field_name, data_type) into the oldest row."""
    LayerField = apps.get_model("layer_manager", "LayerField")
    Layer = apps.get_model("layer_manager", "Layer")
    LayerLayerField = Layer.layer_fields.through

    duplicate_groups = (
        LayerField.objects.order_by()
        .values("field_name", "data_type")
        .annotate(keep_id=Min("id"), row_count=Count("id"))
        .filter(row_count__gt=1)
    )
    for group in duplicate_groups:
        keep_id = group["keep_id"]
        duplicate_ids = list(
            LayerField.objects.filter(
                field_name=group["field_name"], data_type=group["data_type"]
            )
            .exclude(id=keep_id)
            .values_list("id", flat=True)
        )
        duplicate_layer_ids = set(
            LayerLayerField.objects.filter(layerfield_id__in=duplicate_ids).values_list(
                "layer_id", flat=True
            )
        )
        linked_layer_ids = set(
            LayerLayerField.objects.filter(layerfield_id=keep_id).values_list(
                "layer_id", flat=True
            )
        )
        LayerLayerField.objects.bulk_create(
            LayerLayerField(layer_id=layer_id, layerfield_id=keep_id)
            for layer_id in duplicate_layer_ids - linked_layer_ids
        )
        LayerField.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("layer_manager", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_layer_fields, migrations.RunPython.noop),
    ]
