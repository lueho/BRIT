from django.db import migrations, models


def copy_series_to_profile(apps, schema_editor):
    """Preserve the feedstock series as provenance on the result layer."""
    layer = apps.get_model("layer_manager", "Layer")
    layer.objects.filter(feedstock__isnull=False).update(
        sample_series_id=models.F("feedstock_id")
    )


def legacy_feedstock_to_material(apps, schema_editor):
    """Repoint feedstock ids from the series to its material."""
    layer = apps.get_model("layer_manager", "Layer")
    series = apps.get_model("materials", "SampleSeries")
    material_of_series = dict(series.objects.values_list("id", "material_id"))
    for entry in layer.objects.filter(legacy_feedstock_id__isnull=False).iterator():
        entry.feedstock_id = material_of_series.get(entry.legacy_feedstock_id)
        entry.save(update_fields=["feedstock_id"])
    # Flush deferred constraint triggers so the following ALTER TABLEs work.
    schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def material_to_legacy_feedstock(apps, schema_editor):
    """Restore the preserved series into the legacy feedstock column."""
    layer = apps.get_model("layer_manager", "Layer")
    layer.objects.filter(sample_series_id__isnull=False).update(
        legacy_feedstock_id=models.F("sample_series_id")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("layer_manager", "0003_layer_staged"),
        ("materials", "0029_merge_20260922_1559"),
    ]

    operations = [
        migrations.AddField(
            model_name="layer",
            name="sample_series",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                to="materials.sampleseries",
            ),
        ),
        migrations.RunPython(copy_series_to_profile, migrations.RunPython.noop),
        # Rename the series FK aside so the column swap never holds ids that
        # violate whichever foreign key is attached at the time.
        migrations.RenameField(
            model_name="layer",
            old_name="feedstock",
            new_name="legacy_feedstock",
        ),
        migrations.AddField(
            model_name="layer",
            name="feedstock",
            field=models.ForeignKey(
                null=True,
                on_delete=models.CASCADE,
                to="materials.material",
            ),
        ),
        migrations.RunPython(
            legacy_feedstock_to_material, material_to_legacy_feedstock
        ),
        migrations.RemoveField(
            model_name="layer",
            name="legacy_feedstock",
        ),
        migrations.AlterField(
            model_name="layer",
            name="feedstock",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                to="materials.material",
            ),
        ),
    ]
