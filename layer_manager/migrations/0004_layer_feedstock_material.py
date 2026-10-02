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


BACKUP_SCHEMA = "migration_backup"
BACKUP_TABLE = f"{BACKUP_SCHEMA}.layer_manager_0004_collapsed_layers"


def _backup_rows(schema_editor, model, column, ids):
    table = model._meta.db_table
    schema_editor.execute(
        f"INSERT INTO {BACKUP_TABLE} (source_table, payload) "
        f'SELECT %s, to_jsonb(t) FROM "{table}" t WHERE t."{column}" = ANY(%s)',
        [table, list(ids)],
    )


def _restore_rows(schema_editor, model):
    table = model._meta.db_table
    schema_editor.execute(
        f'INSERT INTO "{table}" '
        f'SELECT (jsonb_populate_record(NULL::"{table}", payload)).* '
        f"FROM {BACKUP_TABLE} WHERE source_table = %s ORDER BY ordinal",
        [table],
    )


def _relation_exists(schema_editor, name):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", [name])
        return cursor.fetchone()[0] is not None


def _drop_backup(schema_editor):
    schema_editor.execute(f"DROP TABLE {BACKUP_TABLE}")
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s LIMIT 1",
            [BACKUP_SCHEMA],
        )
        if cursor.fetchone() is None:
            schema_editor.execute(f"DROP SCHEMA {BACKUP_SCHEMA}")


def _layer_models(apps):
    layer = apps.get_model("layer_manager", "Layer")
    return (
        layer,
        layer._meta.get_field("layer_fields").remote_field.through,
        apps.get_model("layer_manager", "LayerAggregatedValue"),
        apps.get_model("layer_manager", "LayerAggregatedDistribution"),
        apps.get_model("layer_manager", "DistributionSet"),
        apps.get_model("layer_manager", "DistributionShare"),
    )


def deduplicate_collapsed_layers(apps, schema_editor):
    """Set aside result layers that collapsed onto the same identity.

    Layers that previously differed only in the feedstock *series* now share
    (scenario, algorithm, material), which breaks ``create_or_replace``'s
    one-layer-per-identity assumption. Keep one row — preferring one that
    still carries a temporal profile. The losers' rows (and dependent
    aggregates, distributions and field links) are copied to
    ``BACKUP_TABLE`` and their dynamic feature tables are moved into
    ``BACKUP_SCHEMA`` so the reverse migration can restore them.
    """
    layer, through, value, distribution, distribution_set, share = _layer_models(apps)
    # _base_manager also sees staged rows, which the default manager hides.
    manager = layer._base_manager
    groups = (
        manager.values("scenario_id", "algorithm_id", "feedstock_id")
        .annotate(n=models.Count("id"))
        .filter(n__gt=1)
    )
    losers = []
    for group in groups:
        group.pop("n")
        layers = sorted(
            manager.filter(**group).values("id", "sample_series_id", "table_name"),
            key=lambda row: (row["sample_series_id"] is None, row["id"]),
        )
        losers.extend(layers[1:])
    if not losers:
        return

    schema_editor.execute(f"CREATE SCHEMA IF NOT EXISTS {BACKUP_SCHEMA}")
    schema_editor.execute(
        f"CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} ("
        "ordinal serial PRIMARY KEY, source_table text NOT NULL, "
        "payload jsonb NOT NULL)"
    )
    layer_ids = [row["id"] for row in losers]
    distribution_ids = list(
        distribution.objects.filter(layer_id__in=layer_ids).values_list("id", flat=True)
    )
    set_ids = list(
        distribution_set.objects.filter(
            aggregated_distribution_id__in=distribution_ids
        ).values_list("id", flat=True)
    )
    _backup_rows(schema_editor, layer, "id", layer_ids)
    _backup_rows(schema_editor, through, "layer_id", layer_ids)
    _backup_rows(schema_editor, value, "layer_id", layer_ids)
    _backup_rows(schema_editor, distribution, "id", distribution_ids)
    _backup_rows(schema_editor, distribution_set, "id", set_ids)
    _backup_rows(schema_editor, share, "distribution_set_id", set_ids)

    manager.filter(id__in=layer_ids).delete()
    for loser in losers:
        table = loser["table_name"].replace('"', "")
        schema_editor.execute(
            f'ALTER TABLE IF EXISTS "{table}" SET SCHEMA {BACKUP_SCHEMA}'
        )


def restore_collapsed_layers(apps, schema_editor):
    """Bring back the layers, their data and feature tables set aside above."""
    if not _relation_exists(schema_editor, BACKUP_TABLE):
        return
    layer_models = _layer_models(apps)
    for model in layer_models:
        _restore_rows(schema_editor, model)
    layer = layer_models[0]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT payload->>'table_name' FROM {BACKUP_TABLE} "
            "WHERE source_table = %s",
            [layer._meta.db_table],
        )
        tables = [row[0].replace('"', "") for row in cursor.fetchall()]
        cursor.execute("SELECT current_schema()")
        target_schema = cursor.fetchone()[0]
    for table in tables:
        schema_editor.execute(
            f'ALTER TABLE IF EXISTS {BACKUP_SCHEMA}."{table}" '
            f'SET SCHEMA "{target_schema}"'
        )
    _drop_backup(schema_editor)
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
        migrations.RunPython(deduplicate_collapsed_layers, restore_collapsed_layers),
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
