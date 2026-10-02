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


def deduplicate_collapsed_layers(apps, schema_editor):
    """Drop result layers that collapsed onto the same identity.

    Layers that previously differed only in the feedstock *series* now share
    (scenario, algorithm, material), which breaks ``create_or_replace``'s
    one-layer-per-identity assumption. Keep one row — preferring one that
    still carries a temporal profile — and drop the dynamic feature tables
    of the losers explicitly, since historical models bypass Layer.delete().
    """
    layer = apps.get_model("layer_manager", "Layer")
    # _base_manager also sees staged rows, which the default manager hides.
    manager = layer._base_manager
    groups = (
        manager.values("scenario_id", "algorithm_id", "feedstock_id")
        .annotate(n=models.Count("id"))
        .filter(n__gt=1)
    )
    for group in groups:
        group.pop("n")
        layers = sorted(
            manager.filter(**group).values("id", "sample_series_id", "table_name"),
            key=lambda row: (row["sample_series_id"] is None, row["id"]),
        )
        for loser in layers[1:]:
            manager.filter(id=loser["id"]).delete()
            table = loser["table_name"].replace('"', "")
            schema_editor.execute(f'DROP TABLE IF EXISTS "{table}"')


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
        # Relax the old column first so reversing the RemoveField below can
        # re-add it empty and let the reverse data step fill it.
        migrations.AlterField(
            model_name="layer",
            name="feedstock",
            field=models.ForeignKey(
                null=True,
                on_delete=models.CASCADE,
                to="materials.sampleseries",
            ),
        ),
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
        migrations.RunPython(deduplicate_collapsed_layers, migrations.RunPython.noop),
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
