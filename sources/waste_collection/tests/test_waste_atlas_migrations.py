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
from django.test.utils import CaptureQueriesContext

from utils.tests.testrunner import serial_test

APP = "waste_atlas"
BASELINE = "0001_squashed_0027"
ORIGINAL_TIP = "0027_move_stored_urls_to_atlas_prefix"
PARTIAL_TIP = "0008_drop_redundant_no_data_color"

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

    def test_originals_remain_on_disk(self):
        loader = MigrationLoader(None)
        for name in HISTORICAL_MIGRATIONS:
            self.assertIn((APP, name), loader.disk_migrations)

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

    def test_baseline_state_matches_original_tip(self):
        plain_loader = MigrationLoader(None, replace_migrations=False)
        loader = MigrationLoader(None)
        original_state = plain_loader.project_state(nodes=[(APP, ORIGINAL_TIP)])
        baseline_state = loader.project_state(nodes=[(APP, BASELINE)])
        original_models = {
            key: state for key, state in original_state.models.items() if key[0] == APP
        }
        baseline_models = {
            key: state for key, state in baseline_state.models.items() if key[0] == APP
        }
        self.assertEqual(original_models, baseline_models)

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

    def test_partial_history_replays_originals_and_preserves_data(self):
        fresh = self._controlled_database()
        old_executor = MigrationExecutor(fresh)
        old_executor.loader = MigrationLoader(fresh, replace_migrations=False)
        old_executor.migrate([(APP, PARTIAL_TIP)])

        historical_apps = old_executor.loader.project_state(
            nodes=[(APP, PARTIAL_TIP)]
        ).apps
        HistoricalMapConfig = historical_apps.get_model(
            APP, "WasteAtlasMapConfiguration"
        )
        HistoricalSettings = historical_apps.get_model(
            APP, "WasteAtlasRenderingSettings"
        )
        custom = HistoricalMapConfig.objects.create(
            key="custom_legacy_map",
            configuration={
                "dataUrl": "/waste_collection/api/waste-atlas/custom/",
                "pageUrl": "/waste_collection/api/waste-atlas/map/custom/",
                "outlineStrokeColor": "#123456",
                "outlineStrokeOpacity": 0.95,
                "outlineStrokeWidth": 7,
                "acpvOutline": {"color": "#123456", "width": 7},
                "nested": {"arbitrary": [1, {"deep": "value"}]},
            },
        )
        singleton = HistoricalSettings.objects.get()
        singleton.quartile_colors = ["#111111", "#222222", "#333333", "#444444"]
        singleton.legend_width = 424
        singleton.save()

        executor = MigrationExecutor(fresh)
        executor.migrate(executor.loader.graph.leaf_nodes(APP))

        applied = self._applied(fresh)
        for name in HISTORICAL_MIGRATIONS:
            self.assertIn((APP, name), applied)
        self.assertIn((APP, BASELINE), applied)

        from sources.waste_collection.waste_atlas.models import (
            WasteAtlasMapConfiguration,
            WasteAtlasRenderingSettings,
        )

        migrated_custom = WasteAtlasMapConfiguration.objects.get(pk=custom.pk)
        self.assertEqual(migrated_custom.key, "custom_legacy_map")
        self.assertEqual(
            migrated_custom.configuration["dataUrl"],
            "/waste_collection/waste-atlas/api/custom/",
        )
        self.assertEqual(
            migrated_custom.configuration["pageUrl"],
            "/waste_collection/waste-atlas/map/custom/",
        )
        self.assertEqual(migrated_custom.configuration["acpvOutlineColor"], "#123456")
        self.assertEqual(migrated_custom.configuration["acpvOutlineWidth"], 7)
        for legacy_key in (
            "outlineStrokeColor",
            "outlineStrokeOpacity",
            "outlineStrokeWidth",
        ):
            self.assertNotIn(legacy_key, migrated_custom.configuration)
        self.assertNotIn("acpvOutlineOpacity", migrated_custom.configuration)
        self.assertEqual(
            migrated_custom.configuration["acpvOutline"],
            {"color": "#123456", "width": 7},
        )
        self.assertEqual(
            migrated_custom.configuration["nested"],
            {"arbitrary": [1, {"deep": "value"}]},
        )

        configurations = _load_default_configurations()
        self._assert_default_rows(configurations)
        connection_rate = WasteAtlasMapConfiguration.objects.get(
            key="connection_rate"
        ).configuration
        self.assertEqual(
            [category["value"] for category in connection_rate["categories"]],
            [
                "full_connection",
                "75-99",
                "50-74",
                "25-49",
                "0-24",
                "no_d2d",
            ],
        )
        self.assertEqual(
            connection_rate["dataUrl"],
            "/waste_collection/waste-atlas/api/connection-rate/",
        )
        for key in ("organic_collection_amount", "organic_waste_ratio"):
            categories = {
                category["value"]: category["label"]
                for category in WasteAtlasMapConfiguration.objects.get(
                    key=key
                ).configuration["categories"]
            }
            self.assertEqual(categories["no_collection"], "No separate collection", key)

        singleton_after = WasteAtlasRenderingSettings.objects.get(pk=1)
        self.assertEqual(
            singleton_after.quartile_colors,
            ["#111111", "#222222", "#333333", "#444444"],
        )
        self.assertEqual(singleton_after.legend_width, 424)

        rows_before = self._atlas_snapshot(fresh)
        call_command("ensure_initial_data", app_label=APP, stdout=io.StringIO())
        executor = MigrationExecutor(fresh)
        executor.migrate(executor.loader.graph.leaf_nodes(APP))
        self.assertEqual(self._atlas_snapshot(fresh), rows_before)

    def test_completed_history_adopts_baseline_without_data_writes(self):
        fresh = self._controlled_database()
        old_executor = MigrationExecutor(fresh)
        old_executor.loader = MigrationLoader(fresh, replace_migrations=False)
        old_executor.migrate([(APP, ORIGINAL_TIP)])

        from sources.waste_collection.waste_atlas.models import (
            WasteAtlasMapConfiguration,
            WasteAtlasRenderingSettings,
        )

        configurations = _load_default_configurations()
        self._assert_default_rows(configurations)

        customized = WasteAtlasMapConfiguration.objects.get(key="connection_rate")
        customized.configuration = {
            **customized.configuration,
            "customFlag": {"x": 1},
        }
        customized.save()
        singleton = WasteAtlasRenderingSettings.objects.get(
            pk=WasteAtlasRenderingSettings.SINGLETON_PK
        )
        singleton.legend_width = 512
        singleton.save()

        # check_replacements already recorded the baseline marker when the
        # original chain completed; drop it to model a database that finished
        # the chain before the baseline existed.
        recorder = MigrationRecorder(fresh)
        recorder.record_unapplied(APP, BASELINE)
        history_before = self._history(fresh)
        self.assertEqual(
            {row["name"] for row in history_before},
            set(HISTORICAL_MIGRATIONS),
        )
        before = self._atlas_snapshot(fresh)

        executor = MigrationExecutor(fresh)
        executor.loader.check_consistent_history(fresh)
        self.assertEqual(
            executor.migration_plan(executor.loader.graph.leaf_nodes(APP)), []
        )
        with CaptureQueriesContext(fresh) as first:
            executor.migrate(executor.loader.graph.leaf_nodes(APP))
        history_after_first = self._history(fresh)
        self.assertEqual(history_after_first[: len(history_before)], history_before)
        marker_rows = history_after_first[len(history_before) :]
        self.assertEqual(len(marker_rows), 1)
        self.assertEqual(
            (marker_rows[0]["app"], marker_rows[0]["name"]), (APP, BASELINE)
        )
        keys = [(row["app"], row["name"]) for row in history_after_first]
        self.assertEqual(len(keys), len(set(keys)))
        with CaptureQueriesContext(fresh) as second:
            executor.migrate(executor.loader.graph.leaf_nodes(APP))
        self.assertEqual(self._history(fresh), history_after_first)

        touched = []
        for captured in (first, second):
            for query in captured.captured_queries:
                if '"waste_atlas' in query["sql"]:
                    touched.append(query["sql"])
        self.assertEqual(touched, [])
        self.assertEqual(before, self._atlas_snapshot(fresh))
