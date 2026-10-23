import io
import json
import uuid
from pathlib import Path

from django.apps import apps
from django.core.cache import cache
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections, migrations
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase

from utils.tests.testrunner import serial_test

APP = "waste_atlas"
BASELINE = "0001_squashed_0027"

HISTORICAL_MIGRATIONS = [
    "0001_initial",
    "0002_seed_map_configurations",
    "0003_seed_target_waste_category",
    "0004_drop_file_base_from_map_configurations",
    "0004_seed_residual_waste_composition_maps",
    "0005_merge_20260730_1555",
    "0006_add_residual_collection_amount_acpv_overlay",
    "0006_wasteatlasrenderingsettings",
    "0007_add_waste_ratio_aggregated_overlay",
    "0007_seed_rendering_settings",
    "0008_drop_redundant_no_data_color",
    "0009_drop_placement_coupled_legend_columns",
    "0010_wasteatlasrenderingsettings_change_boundary_changed_color",
    "0011_wasteatlasrenderingsettings_export_legend_item_flow",
    "0012_wasteatlasrenderingsettings_acpv_hatch_color_and_more",
    "0013_centralize_acpv_marker_appearance",
    "0014_alter_wasteatlasrenderingsettings_export_legend_item_flow",
    "0014_seed_rp_map_configurations",
    "0015_merge_legend_flow_and_rp_configurations",
    "0016_distinguish_no_collection_from_no_door_to_door",
    "0017_disable_connection_rate_quartiles",
    "0018_configure_connection_rate_boundaries",
    "0019_include_all_connection_rates_in_quartiles",
    "0020_reclassify_min_bin_sizes",
    "0021_hide_absent_min_bin_size_categories",
    "0022_add_access_control_legend_note",
    "0023_add_organic_amount_no_collection",
    "0024_group_access_control_export_legend",
    "0025_compact_system_access_control_legend",
    "0026_add_organic_ratio_no_collection",
    "0027_move_stored_urls_to_atlas_prefix",
]

MODEL_ORDER = ["wasteatlasmapconfiguration", "wasteatlasrenderingsettings"]

DEFAULTS_FILE = (
    Path(__file__).resolve().parents[1]
    / "waste_atlas"
    / "initial_map_configurations.json"
)


def _load_default_configurations():
    return json.loads(DEFAULTS_FILE.read_text())


class WasteAtlasBaselineGraphTests(SimpleTestCase):
    """Static checks on the schema-only baseline migration; no database."""

    def test_full_graph_validates_without_missing_nodes_or_cycles(self):
        loader = MigrationLoader(None)
        loader.graph.validate_consistency()
        loader.graph.ensure_not_cyclic()

    def test_baseline_is_initial_and_replaces_exact_originals(self):
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[(APP, BASELINE)]
        self.assertTrue(migration.initial)
        self.assertEqual(
            migration.replaces, [(APP, name) for name in HISTORICAL_MIGRATIONS]
        )
        self.assertEqual(migration.dependencies, [])

    def test_fresh_plan_contains_only_baseline(self):
        loader = MigrationLoader(None)
        key = (APP, BASELINE)
        self.assertEqual(loader.graph.leaf_nodes(APP), [key])
        plan = [node for node in loader.graph.forwards_plan(key) if node[0] == APP]
        self.assertEqual(plan, [key])

    def test_baseline_operations_are_schema_only(self):
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[(APP, BASELINE)]
        creates = [
            op for op in migration.operations if isinstance(op, migrations.CreateModel)
        ]
        self.assertEqual([op.name.lower() for op in creates], MODEL_ORDER)
        for operation in migration.operations:
            self.assertIsInstance(operation, migrations.CreateModel)
            self.assertNotIsInstance(
                operation, (migrations.RunPython, migrations.RunSQL)
            )

    def test_migrated_state_matches_current_models(self):
        loader = MigrationLoader(None)
        migrated_state = loader.project_state()
        current_state = ProjectState.from_apps(apps)
        detector = MigrationAutodetector(migrated_state, current_state)
        changes = detector._detect_changes()
        self.assertFalse(changes.get(APP), changes.get(APP))


@serial_test
class WasteAtlasMigrationRuntimeTests(SimpleTestCase):
    """Real migrations against unique disposable physical databases.

    Each test creates a dedicated database so migration plans run against a
    real PostGIS layout instead of a scratch schema inside the shared test
    database. Only the uniquely named database is dropped afterwards.
    """

    databases = {"default"}

    def _controlled_database(self):
        original = connections[DEFAULT_DB_ALIAS]
        self.assertFalse(original.in_atomic_block)

        name = f"test_waste_atlas_{uuid.uuid4().hex[:16]}"
        admin = connections.create_connection(DEFAULT_DB_ALIAS)
        admin.settings_dict = dict(admin.settings_dict, NAME="postgres")
        fresh = connections.create_connection(DEFAULT_DB_ALIAS)
        fresh.settings_dict = dict(fresh.settings_dict, NAME=name)
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}" WITH TEMPLATE template0')

        def cleanup():
            connections[DEFAULT_DB_ALIAS] = original
            fresh.close()
            with admin.cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
            admin.close()
            cache.clear()

        self.addCleanup(cleanup)
        fresh.prepare_database()
        connections[DEFAULT_DB_ALIAS] = fresh
        cache.clear()
        return fresh

    def _applied(self, fresh):
        return set(MigrationRecorder(fresh).applied_migrations())

    def _history(self, fresh):
        return list(
            MigrationRecorder(fresh)
            .migration_qs.order_by("id")
            .values("id", "app", "name", "applied")
        )

    def _atlas_snapshot(self, fresh):
        tables = {}
        with fresh.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND "
                "table_name LIKE 'waste_atlas!_%' ESCAPE '!'"
            )
            names = [row[0] for row in cursor.fetchall()]
        for name in names:
            with fresh.cursor() as cursor:
                cursor.execute(f'SELECT * FROM "{name}" ORDER BY 1')
                tables[name] = sorted(cursor.fetchall())
        return tables

    def _assert_default_rows(self, configurations):
        from sources.waste_collection.waste_atlas.models import (
            WasteAtlasMapConfiguration,
        )

        for key, configuration in configurations.items():
            with self.subTest(key=key):
                self.assertEqual(
                    WasteAtlasMapConfiguration.objects.get(key=key).configuration,
                    configuration,
                )

    def test_fresh_baseline_creates_empty_schema_then_initializer_seeds(self):
        fresh = self._controlled_database()
        executor = MigrationExecutor(fresh)
        executor.migrate([(APP, BASELINE)])

        from sources.waste_collection.waste_atlas.models import (
            WasteAtlasMapConfiguration,
            WasteAtlasRenderingSettings,
        )

        # Django records the baseline and every replaced name as applied,
        # while only the baseline's schema operations actually run.
        self.assertEqual(
            self._applied(fresh),
            {(APP, BASELINE)} | {(APP, name) for name in HISTORICAL_MIGRATIONS},
        )
        self.assertFalse(WasteAtlasMapConfiguration.objects.exists())
        self.assertFalse(WasteAtlasRenderingSettings.objects.exists())

        out = io.StringIO()
        call_command("ensure_initial_data", app_label=APP, stdout=out)

        configurations = _load_default_configurations()
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.count(), len(configurations)
        )
        self._assert_default_rows(configurations)
        self.assertEqual(WasteAtlasRenderingSettings.objects.count(), 1)
        settings_row = WasteAtlasRenderingSettings.objects.get(
            pk=WasteAtlasRenderingSettings.SINGLETON_PK
        )
        self.assertEqual(settings_row.legend_width, 300)
        self.assertEqual(len(settings_row.quartile_colors), 4)
