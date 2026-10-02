from collections import defaultdict

from django.db import migrations, models


def copy_series_to_profile(apps, schema_editor):
    """Preserve the feedstock series as the optional temporal profile."""
    config = apps.get_model("inventories", "ScenarioInventoryConfiguration")
    config.objects.filter(feedstock__isnull=False).update(
        sample_series_id=models.F("feedstock_id")
    )


def legacy_feedstock_to_material(apps, schema_editor):
    """Repoint feedstock ids from the series to its material."""
    config = apps.get_model("inventories", "ScenarioInventoryConfiguration")
    series = apps.get_model("materials", "SampleSeries")
    material_of_series = dict(series.objects.values_list("id", "material_id"))
    for entry in config.objects.filter(legacy_feedstock_id__isnull=False).iterator():
        entry.feedstock_id = material_of_series.get(entry.legacy_feedstock_id)
        entry.save(update_fields=["feedstock_id"])
    # Flush deferred constraint triggers so the following ALTER TABLEs work.
    schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def deduplicate_collapsed_configurations(apps, schema_editor):
    """Collapse configs that became identical when feedstock became Material.

    Rows that previously differed only in the feedstock *series* now share
    (scenario, material, algorithm, parameter) — which is_valid_configuration
    rejects — and a single temporal profile must win per group so the
    execution plan stays unambiguous. The profile a surviving result layer
    references is kept; otherwise the lowest series id.
    """
    config = apps.get_model("inventories", "ScenarioInventoryConfiguration")
    layer = apps.get_model("layer_manager", "Layer")
    rows = config.objects.order_by("id").values_list(
        "id",
        "scenario_id",
        "feedstock_id",
        "inventory_algorithm_id",
        "inventory_parameter_id",
        "sample_series_id",
    )
    groups = defaultdict(list)
    for row in rows:
        groups[row[1:4]].append(row)
    for (scenario_id, feedstock_id, algorithm_id), group in groups.items():
        series_ids = {row[5] for row in group}
        parameter_ids = [row[4] for row in group]
        if len(series_ids) <= 1 and len(parameter_ids) == len(set(parameter_ids)):
            continue
        layer_series = [
            series_id
            for series_id in layer._base_manager.filter(
                scenario_id=scenario_id,
                algorithm_id=algorithm_id,
                feedstock_id=feedstock_id,
            ).values_list("sample_series_id", flat=True)
            if series_id is not None
        ]
        non_null_series = sorted(s for s in series_ids if s is not None)
        canonical = (
            layer_series[0]
            if layer_series
            else (non_null_series[0] if non_null_series else None)
        )
        by_parameter = defaultdict(list)
        for row in group:
            by_parameter[row[4]].append(row)
        keep_ids, drop_ids = [], []
        for parameter_rows in by_parameter.values():
            preferred = [r for r in parameter_rows if r[5] == canonical]
            keep_ids.append((preferred or parameter_rows)[0][0])
        keep_set = set(keep_ids)
        drop_ids = [r[0] for r in group if r[0] not in keep_set]
        config.objects.filter(id__in=drop_ids).delete()
        config.objects.filter(id__in=keep_ids).exclude(
            sample_series_id=canonical
        ).update(sample_series_id=canonical)


def material_to_legacy_feedstock(apps, schema_editor):
    """Restore the preserved series into the legacy feedstock column."""
    config = apps.get_model("inventories", "ScenarioInventoryConfiguration")
    config.objects.filter(sample_series_id__isnull=False).update(
        legacy_feedstock_id=models.F("sample_series_id")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("inventories", "0008_inventoryalgorithmparametervalue_is_custom"),
        ("materials", "0029_merge_20260922_1559"),
        # Layers must already carry Material feedstocks so their preserved
        # series can be preferred as the canonical temporal profile.
        ("layer_manager", "0004_layer_feedstock_material"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenarioinventoryconfiguration",
            name="sample_series",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Optional temporal profile for algorithms that need "
                    "seasonal data. Most inventories only need the material "
                    "itself."
                ),
                null=True,
                on_delete=models.SET_NULL,
                to="materials.sampleseries",
            ),
        ),
        migrations.RunPython(copy_series_to_profile, migrations.RunPython.noop),
        # Rename the series FK aside so the column swap never holds ids that
        # violate whichever foreign key is attached at the time.
        migrations.RenameField(
            model_name="scenarioinventoryconfiguration",
            old_name="feedstock",
            new_name="legacy_feedstock",
        ),
        migrations.AddField(
            model_name="scenarioinventoryconfiguration",
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
        migrations.RunPython(
            deduplicate_collapsed_configurations, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="scenarioinventoryconfiguration",
            name="legacy_feedstock",
        ),
    ]
