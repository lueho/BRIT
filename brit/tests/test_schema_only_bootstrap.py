import contextlib
import io
import os
import uuid
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections, migrations
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext

import utils.object_management.models as object_management_models
import utils.object_management.signals as object_management_signals

BASELINES = {
    "properties": "0001_squashed_0010",
    "materials": "0001_squashed_0032",
    "waste_atlas": "0001_squashed_0027",
    "maps": "0001_squashed_0020",
    "processes": "0001_squashed_0016",
    "inventories": "0001_squashed_0008",
    "distributions": "0001_squashed_0004",
    "layer_manager": "0001_squashed_0004",
    "object_management": "0001_squashed_0006",
    "closecycle": "0001_squashed_0007",
    "population": "0001_squashed_0002",
    "waste_collection": "0001_squashed_0008",
}

ORIGINALS = {
    "properties": [
        "0001_initial",
        "0002_property_approved_at_property_approved_by_and_more",
        "0003_alter_property_publication_status_and_more",
        "0004_alter_property_options",
        "0005_alter_property_publication_status_and_more",
        "0005_unit_symbol",
        "0006_merge_20260217_0951",
        "0007_alter_property_options",
        "0008_materialproperty_unit_optional",
        "0009_collection_point_property",
        "0010_remove_property_unit",
    ],
    "waste_atlas": [
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
    ],
    "maps": [
        "0001_initial",
        "0002_attribute_approved_at_attribute_approved_by_and_more",
        "0003_alter_attribute_publication_status_and_more",
        "0004_region_type_field",
        "0005_alter_attribute_publication_status_and_more",
        "0006_split_categorical_attributes",
        "0007_alter_attribute_options",
        "0008_regionattributevalue_unit",
        "0009_regionproperty",
        "0010_regionattributevalue_regionproperty",
        "0011_alter_regionproperty_options",
        "0012_geodataset_runtime_metadata",
        "0013_alter_geodatasetcolumnpolicy_id_and_more",
        "0014_alter_geodatasetcolumnpolicy_options_and_more",
        "0015_geodatasetcolumnpolicy_is_popup",
        "0016_alter_nutsregion_options_nutsvintage_and_more",
        "0017_catchment_revisions",
        "0018_remove_regionproperty_unit_and_more",
        "0019_region_name_en",
        "0020_delete_attribute",
    ],
    "processes": [
        "0001_initial",
        "0002_processcategory_process_processinforesource_and_more",
        "0003_refine_process_models",
        "0004_rename_processmat_process_r_0d0e2b_idx_processes_p_process_807014_idx_and_more",
        "0005_add_moderation_permissions",
        "0006_alter_process_publication_status_and_more",
        "0007_alter_process_options_process_author_and_more",
        "0008_process_supplementary_document",
        "0009_processcategory_supplementary_document",
        "0010_process_image_metadata",
        "0011_process_authors",
        "0012_move_process_contact_details_to_authors",
        "0013_process_sources",
        "0014_process_author_source_formsets",
        "0015_processauthor_ordering",
        "0016_remove_process_parent",
    ],
    "inventories": [
        "0001_initial",
        "0002_scenario_approved_at_scenario_approved_by_and_more",
        "0003_alter_scenario_publication_status",
        "0004_alter_scenario_publication_status",
        "0005_update_greenhouses_source_module",
        "0006_alter_scenariostatus_options",
        "0007_scenariostatus_failed_algorithm_and_more",
        "0008_inventoryalgorithmparametervalue_is_custom",
    ],
    "distributions": [
        "0001_initial",
        "0002_period_approved_at_period_approved_by_and_more",
        "0003_alter_period_publication_status_and_more",
        "0004_alter_period_publication_status_and_more",
    ],
    "layer_manager": [
        "0001_initial",
        "0002_unique_layer_field_name_data_type",
        "0003_layer_staged",
        "0004_layer_feedstock_material",
    ],
    "object_management": [
        "0001_initial",
        "0002_reviewlog",
        "0003_alter_reviewaction_action_delete_reviewlog",
        "0004_objecteditorgrant",
        "0005_objectgroupeditorgrant",
        "0005_reviewnotificationmute",
        "0006_merge_review_notification_mute",
    ],
    "closecycle": [
        "0001_initial",
        "0002_showcase_approved_at_showcase_approved_by_and_more",
        "0003_alter_showcase_publication_status",
        "0004_alter_showcase_publication_status",
        "0005_showcase_catchment_showcase_sample_series_and_more",
        "0006_showcase_geom",
        "0007_showcase_theme",
    ],
    "population": [
        "0001_initial",
        "0002_alter_populationestimate_region_and_more",
    ],
    "waste_collection": [
        "0001_initial",
        "0002_rename_sortingmethod_binconfiguration_and_more",
        "0003_fix_sweden_2024_valid_until",
        "0004_add_access_control_to_collection",
        "0005_replace_access_control_with_bp_pap",
        "0006_rename_connection_type_to_participation_policy",
        "0007_alter_collectioncountoptions_options",
        "0008_collection_list_order_index",
    ],
    "materials": [
        "0001_initial",
        "0002_analyticalmethod_approved_at_and_more",
        "0003_alter_analyticalmethod_publication_status_and_more",
        "0004_alter_materialproperty_options_and_more",
        "0005_alter_analyticalmethod_publication_status_and_more",
        "0005_remove_materialpropertyvalue_name_description",
        "0006_materialpropertyvalue_unit",
        "0007_merge_20260217_0951",
        "0008_basematerial_comparable_component",
        "0009_materialproperty_comparable_property",
        "0010_materialpropertyvalue_basis_component",
        "0011_make_standard_deviation_optional",
        "0012_alter_analyticalmethod_sources_and_more",
        "0013_materialpropertyvalue_sample",
        "0014_remove_sample_properties",
        "0015_alter_materialcategory_options_and_more",
        "0016_delete_weightshare",
        "0017_unique_published_basematerial_name_type",
        "0018_materialproperty_configure_allowed_units",
        "0019_materialproperty_unit_optional",
        "0020_sample_image_metadata",
        "0021_sample_time_labels",
        "0022_sample_datetime_precision",
        "0023_remove_component_kind",
        "0024_sampleexternalrecord_and_more",
        "0025_alter_basematerial_unique_together",
        "0026_basematerial_is_aggregate",
        "0027_materialcomponentgroup_is_compositional",
        "0028_remove_materialproperty_unit",
        "0028_samplegroup_sample_sample_groups",
        "0029_merge_20260922_1559",
        "0030_product_material_category",
        "0031_sample_region_sample_site",
        "0032_sampleauthor_sample_authors_and_more",
    ],
}

ORIGINAL_TIPS = {
    "properties": "0010_remove_property_unit",
    "materials": "0032_sampleauthor_sample_authors_and_more",
    "waste_atlas": "0027_move_stored_urls_to_atlas_prefix",
    "maps": "0020_delete_attribute",
    "processes": "0016_remove_process_parent",
    "inventories": "0008_inventoryalgorithmparametervalue_is_custom",
    "distributions": "0004_alter_period_publication_status_and_more",
    "layer_manager": "0004_layer_feedstock_material",
    "object_management": "0006_merge_review_notification_mute",
    "closecycle": "0007_showcase_theme",
    "population": "0002_alter_populationestimate_region_and_more",
    "waste_collection": "0008_collection_list_order_index",
}

MODEL_ORDER = {
    "properties": ["property", "unit"],
    "materials": [
        "analyticalmethod",
        "basematerial",
        "materialcategory",
        "materialcomponentgroup",
        "materialpropertygroup",
        "samplegroup",
        "material",
        "materialcomponent",
        "materialproperty",
        "sampleseries",
        "sample",
        "componentmeasurement",
        "composition",
        "materialpropertyvalue",
        "sampleauthor",
        "sampleexternalrecord",
    ],
    "waste_atlas": ["wasteatlasmapconfiguration", "wasteatlasrenderingsettings"],
    "maps": [
        "geopolygon",
        "region",
        "catchment",
        "categoricalattribute",
        "geodataset",
        "geodatasetruntimeconfiguration",
        "georeferencedcatchment",
        "georeferencedregion",
        "nutsregion",
        "location",
        "mapconfiguration",
        "maplayerconfiguration",
        "maplayerstyle",
        "modelmapconfiguration",
        "nutsvintage",
        "regionattributetextvalue",
        "regionproperty",
        "regionattributevalue",
        "geodatasetcolumnpolicy",
        "georeferencednutsregion",
        "lauregion",
        "catchmentrevision",
    ],
    "processes": [
        "apppermission",
        "process",
        "processauthor",
        "processcategory",
        "processinforesource",
        "processlink",
        "processmaterial",
        "processoperatingparameter",
        "processsource",
    ],
    "inventories": [
        "inventoryalgorithm",
        "inventoryalgorithmparameter",
        "inventoryalgorithmparametervalue",
        "scenario",
        "runningtask",
        "inventoryamountshare",
        "scenarioinventoryconfiguration",
        "scenariostatus",
    ],
    "distributions": ["temporaldistribution", "timestep", "period"],
    "layer_manager": [
        "distributionset",
        "distributionshare",
        "layer",
        "layeraggregateddistribution",
        "layeraggregatedvalue",
        "layerfield",
    ],
    "object_management": [
        "objecteditorgrant",
        "objectgroupeditorgrant",
        "reviewaction",
        "reviewnotificationmute",
    ],
    "closecycle": [
        "biogasplantssweden",
        "showcase",
        "showcasematerial",
        "showcaseprocess",
    ],
    "population": [
        "populationdataset",
        "populationestimate",
        "populationimportrun",
        "populationobservation",
        "populationestimatecomponent",
    ],
    "waste_collection": [
        "collectioncatchment",
        "collectionseason",
        "wasteflyer",
        "wastecomponent",
        "binconfiguration",
        "collection",
        "aggregatedcollectionpropertyvalue",
        "collectionfrequency",
        "collectioncountoptions",
        "collectionsystem",
        "collector",
        "feesystem",
        "wastecategory",
        "collectionpropertyvalue",
    ],
}

BASELINE_DEPENDENCIES = {
    "properties": [migrations.swappable_dependency(settings.AUTH_USER_MODEL)],
    "materials": [
        ("bibliography", "0001_squashed_0012"),
        ("distributions", "0001_squashed_0004"),
        ("maps", "0001_squashed_0020"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "waste_atlas": [],
    "maps": [
        ("bibliography", "0001_squashed_0012"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "processes": [
        ("bibliography", "0001_squashed_0012"),
        ("materials", "0001_squashed_0032"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "inventories": [
        ("bibliography", "0001_squashed_0012"),
        ("distributions", "0001_squashed_0004"),
        ("maps", "0001_squashed_0020"),
        ("materials", "0001_squashed_0032"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "distributions": [migrations.swappable_dependency(settings.AUTH_USER_MODEL)],
    "layer_manager": [
        ("distributions", "0001_squashed_0004"),
        ("inventories", "0001_squashed_0008"),
        ("materials", "0001_squashed_0032"),
    ],
    "object_management": [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "closecycle": [
        ("maps", "0001_squashed_0020"),
        ("materials", "0001_squashed_0032"),
        ("processes", "0001_squashed_0016"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
    "population": [
        ("bibliography", "0001_squashed_0012"),
        ("maps", "0001_squashed_0020"),
    ],
    "waste_collection": [
        ("bibliography", "0001_squashed_0012"),
        ("distributions", "0001_squashed_0004"),
        ("maps", "0001_squashed_0020"),
        ("materials", "0001_squashed_0032"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ],
}


class SchemaOnlyBaselineGraphTests(SimpleTestCase):
    """Static checks on the schema-only replacement migrations; no database."""

    def test_full_graph_validates_without_missing_nodes_or_cycles(self):
        loader = MigrationLoader(None)
        loader.graph.validate_consistency()
        loader.graph.ensure_not_cyclic()
        self.assertFalse(loader.detect_conflicts())

    def test_baselines_are_initial_and_replace_exact_originals(self):
        loader = MigrationLoader(None)
        for app, baseline in BASELINES.items():
            with self.subTest(app=app):
                migration = loader.disk_migrations[(app, baseline)]
                self.assertTrue(migration.initial)
                self.assertEqual(
                    migration.replaces,
                    [(app, name) for name in ORIGINALS[app]],
                )

    def test_originals_remain_on_disk(self):
        loader = MigrationLoader(None)
        for app, names in ORIGINALS.items():
            for name in names:
                self.assertIn((app, name), loader.disk_migrations)

    def test_baseline_dependencies(self):
        loader = MigrationLoader(None)
        for app, expected in BASELINE_DEPENDENCIES.items():
            with self.subTest(app=app):
                baseline = loader.disk_migrations[(app, BASELINES[app])]
                self.assertCountEqual(baseline.dependencies, expected)

    def test_fresh_plan_contains_only_baseline_per_app(self):
        loader = MigrationLoader(None)
        for app, baseline in BASELINES.items():
            with self.subTest(app=app):
                key = (app, baseline)
                plan = [
                    node for node in loader.graph.forwards_plan(key) if node[0] == app
                ]
                self.assertEqual(plan, [key])
                (leaf,) = loader.graph.leaf_nodes(app)
                full_plan = [
                    node for node in loader.graph.forwards_plan(leaf) if node[0] == app
                ]
                self.assertEqual(full_plan[0], key)
                self.assertFalse(
                    {(app, name) for name in ORIGINALS[app]} & set(full_plan)
                )

    def test_baseline_operations_are_schema_only(self):
        loader = MigrationLoader(None)
        for app, baseline in BASELINES.items():
            migration = loader.disk_migrations[(app, baseline)]
            creates = [
                op
                for op in migration.operations
                if isinstance(op, migrations.CreateModel)
            ]
            self.assertEqual(
                [op.name.lower() for op in creates],
                MODEL_ORDER[app],
                app,
            )
            for operation in migration.operations:
                self.assertNotIsInstance(
                    operation, (migrations.RunPython, migrations.RunSQL)
                )
                if isinstance(operation, migrations.AddField):
                    field = operation.field
                    self.assertTrue(
                        field.many_to_many
                        or field.null
                        or not (field.has_default() and callable(field.default)),
                        f"{app} AddField {operation.name} evaluates a "
                        "callable default during schema setup",
                    )

    def test_baseline_state_matches_original_tip_per_app(self):
        plain_loader = MigrationLoader(None, replace_migrations=False)
        loader = MigrationLoader(None)
        for app in BASELINES:
            with self.subTest(app=app):
                original_state = plain_loader.project_state(
                    nodes=[(app, ORIGINAL_TIPS[app])]
                )
                baseline_state = loader.project_state(nodes=[(app, BASELINES[app])])
                original_models = {
                    key: state
                    for key, state in original_state.models.items()
                    if key[0] == app
                }
                baseline_models = {
                    key: state
                    for key, state in baseline_state.models.items()
                    if key[0] == app
                }
                self.assertEqual(original_models, baseline_models)

    def test_migrated_state_matches_current_models(self):
        loader = MigrationLoader(None)
        migrated_state = loader.project_state()
        current_state = ProjectState.from_apps(apps)
        detector = MigrationAutodetector(migrated_state, current_state)
        changes = detector._detect_changes()
        for app in BASELINES:
            with self.subTest(app=app):
                self.assertFalse(changes.get(app), changes.get(app))


class ControlledDatabaseBootstrapBase(SimpleTestCase):
    """Shared plumbing for bootstrap tests on disposable databases.

    Each test creates a dedicated database so migrations run on a real
    PostGIS layout instead of a scratch schema inside the shared test
    database. Only the uniquely named database is dropped afterwards.
    Subclasses hold one test each so the parallel test runner distributes
    the expensive full-migration runs across workers; the disposable
    databases are uniquely named and the swapped default connection is
    restored on cleanup, so no serial execution is required.
    """

    databases = {"default"}

    def _controlled_database(self):
        original = connections[DEFAULT_DB_ALIAS]
        self.assertFalse(original.in_atomic_block)

        name = f"test_schema_only_{uuid.uuid4().hex[:16]}"
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

        self.addCleanup(cleanup)
        fresh.prepare_database()
        connections[DEFAULT_DB_ALIAS] = fresh
        return fresh

    def _isolated_caches(self):
        stack = contextlib.ExitStack()
        stack.enter_context(
            mock.patch.dict(object_management_models._default_owner_pk_cache)
        )
        object_management_models._default_owner_pk_cache.clear()
        stack.enter_context(
            mock.patch.object(
                object_management_signals, "_moderation_permissions_loaded", set()
            )
        )
        ContentType.objects.clear_cache()
        stack.callback(ContentType.objects.clear_cache)
        return stack

    def _run_bootstrap(self):
        environment = {
            "ADMIN_USERNAME": "schema-admin",
            "ADMIN_PASSWORD": "adm-secret",
        }
        with mock.patch.dict(os.environ, environment):
            call_command(
                "bootstrap_database", stdout=io.StringIO(), stderr=io.StringIO()
            )

    def _row_count(self, fresh, table):
        with fresh.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cursor.fetchone()[0]

    def _snapshot(self, fresh):
        tables = {}
        with fresh.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND ("
                "table_name LIKE 'materials!_%' ESCAPE '!' OR "
                "table_name LIKE 'properties!_%' ESCAPE '!' OR "
                "table_name = 'auth_user')"
            )
            names = [row[0] for row in cursor.fetchall()]
        for name in names:
            with fresh.cursor() as cursor:
                cursor.execute(f'SELECT * FROM "{name}" ORDER BY 1')
                tables[name] = sorted(cursor.fetchall())
        return tables

    def _applied(self, fresh):
        return set(MigrationRecorder(fresh).applied_migrations())


class FreshBootstrapSchemaTests(ControlledDatabaseBootstrapBase):
    @override_settings(
        DEFAULT_OBJECT_OWNER_USERNAME="schema-owner",
        DEFAULT_OWNER_USERNAME="legacy-owner",
    )
    def test_fresh_bootstrap_schema_then_required_defaults(self):
        fresh = self._controlled_database()
        with self._isolated_caches():

            def fail(*args, **kwargs):
                raise AssertionError("default getter evaluated during DDL")

            with (
                mock.patch.object(
                    object_management_models, "get_default_owner", side_effect=fail
                ),
                mock.patch(
                    "utils.properties.models.get_default_owner", side_effect=fail
                ),
            ):
                executor = MigrationExecutor(fresh)
                executor.migrate(executor.loader.graph.leaf_nodes())

            for table in (
                "auth_user",
                "properties_unit",
                "properties_property",
                "materials_materialcategory",
                "materials_basematerial",
            ):
                self.assertEqual(self._row_count(fresh, table), 0, table)

            self._run_bootstrap()

            from django.contrib.auth.models import User

            from maps.models import GeoDataset, NutsVintage
            from materials.models import (
                MaterialCategory,
                MaterialComponent,
                MaterialComponentGroup,
            )
            from sources.waste_collection.models import Collection
            from utils.properties.models import Property, Unit

            owner = User.objects.get(username="schema-owner")
            no_unit = Unit.objects.get(owner=owner, name="No unit")
            point_property = Property.objects.get(
                owner=owner, name="number of collection points"
            )
            self.assertEqual(point_property.publication_status, "published")
            self.assertEqual(list(point_property.allowed_units.all()), [no_unit])
            product = MaterialCategory.objects.get(owner=owner, name="Product")
            self.assertEqual(product.publication_status, "published")
            MaterialComponentGroup.objects.get(name="Total Material")
            MaterialComponent.objects.get(name="Fresh Matter (FM)")
            MaterialComponent.objects.get(name="Other")
            self.assertFalse(GeoDataset.objects.exists())
            self.assertFalse(Collection.objects.exists())
            self.assertEqual(NutsVintage.current().year, 2021)

            admin = User.objects.get(username="schema-admin")
            self.assertTrue(admin.check_password("adm-secret"))

            custom_unit = Unit.objects.create(owner=owner, name="custom unit")
            point_property.allowed_units.set([custom_unit])
            product.description = "custom product description"
            product.publication_status = "private"
            product.save()
            ids = (
                point_property.pk,
                product.pk,
                no_unit.pk,
                admin.pk,
            )

            self._run_bootstrap()

            point_property.refresh_from_db()
            product.refresh_from_db()
            admin.refresh_from_db()
            self.assertEqual(list(point_property.allowed_units.all()), [custom_unit])
            self.assertEqual(product.description, "custom product description")
            self.assertEqual(product.publication_status, "private")
            self.assertTrue(admin.check_password("adm-secret"))
            self.assertEqual(
                ids,
                (
                    point_property.pk,
                    product.pk,
                    no_unit.pk,
                    admin.pk,
                ),
            )


class PartialLegacyHistoryBootstrapTests(ControlledDatabaseBootstrapBase):
    @override_settings(
        DEFAULT_OBJECT_OWNER_USERNAME="schema-owner",
        DEFAULT_OWNER_USERNAME="legacy-owner",
    )
    def test_partial_legacy_history_uses_legacy_stages(self):
        from brit.management.commands.bootstrap_database import Command

        fresh = self._controlled_database()
        with self._isolated_caches():
            partial_tip = (
                "materials",
                "0005_remove_materialpropertyvalue_name_description",
            )
            old_executor = MigrationExecutor(fresh)
            old_executor.loader = MigrationLoader(fresh, replace_migrations=False)
            old_executor.migrate([partial_tip])

            historical_apps = old_executor.loader.project_state(
                nodes=[partial_tip]
            ).apps
            HistoricalUser = historical_apps.get_model("auth", "User")
            HistoricalMaterial = historical_apps.get_model("materials", "Material")
            legacy_owner = HistoricalUser.objects.create(
                username="legacy-material-owner",
                password=make_password("legacy-secret"),
            )
            material = HistoricalMaterial.objects.create(
                name="Legacy Material",
                type="material",
                publication_status="private",
                description="custom legacy description",
                owner_id=legacy_owner.pk,
            )

            self.assertTrue(Command()._requires_legacy_bootstrap())
            with mock.patch(
                "brit.management.commands.bootstrap_database.call_command",
                wraps=call_command,
            ) as staged:
                self._run_bootstrap()
            self.assertEqual(
                [
                    (call.args[0], call.args[1:], call.kwargs.get("app_label"))
                    for call in staged.call_args_list
                ],
                [
                    ("migrate", ("auth",), None),
                    ("ensure_initial_data", (), "users"),
                    ("ensure_initial_data", (), "object_management"),
                    ("migrate", ("properties",), None),
                    ("ensure_initial_data", (), "properties"),
                    ("migrate", (), None),
                    ("ensure_initial_data", (), None),
                ],
            )

            from django.contrib.auth.models import User

            from materials.models import Material

            owner = User.objects.get(pk=legacy_owner.pk)
            self.assertTrue(owner.check_password("legacy-secret"))
            migrated = Material.objects.get(pk=material.pk)
            self.assertEqual(migrated.name, "Legacy Material")
            self.assertEqual(migrated.owner_id, legacy_owner.pk)
            self.assertEqual(migrated.description, "custom legacy description")

            applied = self._applied(fresh)
            for app, names in ORIGINALS.items():
                for name in names:
                    self.assertIn((app, name), applied)
            for app, baseline in BASELINES.items():
                self.assertIn((app, baseline), applied)

            self.assertFalse(Command()._requires_legacy_bootstrap())
            with mock.patch(
                "brit.management.commands.bootstrap_database.call_command",
                wraps=call_command,
            ) as staged:
                self._run_bootstrap()
            self.assertEqual(
                [
                    (call.args[0], call.args[1:], call.kwargs.get("app_label"))
                    for call in staged.call_args_list
                ],
                [("migrate", (), None), ("ensure_initial_data", (), None)],
            )

            self._run_bootstrap()
            migrated.refresh_from_db()
            self.assertEqual(migrated.name, "Legacy Material")
            self.assertEqual(migrated.description, "custom legacy description")


class AdoptedHistoryBootstrapTests(ControlledDatabaseBootstrapBase):
    @override_settings(
        DEFAULT_OBJECT_OWNER_USERNAME="schema-owner",
        DEFAULT_OWNER_USERNAME="legacy-owner",
    )
    def test_adopted_history_keeps_data_and_only_restores_markers(self):
        fresh = self._controlled_database()
        with self._isolated_caches():
            executor = MigrationExecutor(fresh)
            executor.migrate(executor.loader.graph.leaf_nodes())
            self._run_bootstrap()

            from django.contrib.auth.models import User

            from materials.models import (
                Material,
                MaterialProperty,
                MaterialPropertyValue,
                Sample,
                SampleGroup,
                SampleSeries,
            )
            from utils.properties.models import Unit

            owner = User.objects.get(username="schema-owner")
            unit = Unit.objects.get(owner=owner, name="No unit")
            material = Material.objects.create(
                name="Adopted Material",
                publication_status="published",
                owner=owner,
            )
            series = SampleSeries.objects.create(
                name="Adopted Series", material=material, owner=owner
            )
            sample = Sample.objects.create(
                name="Adopted Sample",
                material=material,
                series=series,
                owner=owner,
            )
            group = SampleGroup.objects.create(name="Adopted Group", owner=owner)
            sample.sample_groups.add(group)
            prop = MaterialProperty.objects.create(name="Adopted Property", owner=owner)
            prop.allowed_units.add(unit)
            MaterialPropertyValue.objects.create(
                property=prop,
                sample=sample,
                unit=unit,
                average=1.5,
                owner=owner,
            )

            recorder = MigrationRecorder(fresh)
            for app, baseline in BASELINES.items():
                recorder.record_unapplied(app, baseline)

            before = self._snapshot(fresh)
            applied_before = self._applied(fresh)
            history_before = list(
                recorder.migration_qs.order_by("id").values(
                    "id", "app", "name", "applied"
                )
            )
            markers = set(BASELINES.items())

            executor = MigrationExecutor(fresh)
            executor.loader.check_consistent_history(fresh)
            self.assertEqual(
                executor.migration_plan(executor.loader.graph.leaf_nodes()), []
            )
            with CaptureQueriesContext(fresh) as first:
                executor.migrate(executor.loader.graph.leaf_nodes())
            history_after_first = list(
                recorder.migration_qs.order_by("id").values(
                    "id", "app", "name", "applied"
                )
            )
            self.assertEqual(history_after_first[: len(history_before)], history_before)
            marker_rows = history_after_first[len(history_before) :]
            self.assertEqual(len(marker_rows), len(markers))
            self.assertEqual(
                {(row["app"], row["name"]) for row in marker_rows}, markers
            )
            keys = [(row["app"], row["name"]) for row in history_after_first]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertEqual(self._applied(fresh), applied_before | markers)
            with CaptureQueriesContext(fresh) as second:
                executor.migrate(executor.loader.graph.leaf_nodes())
            history_after_second = list(
                recorder.migration_qs.order_by("id").values(
                    "id", "app", "name", "applied"
                )
            )
            self.assertEqual(history_after_second, history_after_first)
            self.assertEqual(self._applied(fresh), applied_before | markers)

            touched = []
            for captured in (first, second):
                for query in captured.captured_queries:
                    sql = query["sql"]
                    if sql.lstrip().startswith(
                        ("CREATE TABLE", "ALTER TABLE", "DROP TABLE", "CREATE INDEX")
                    ):
                        touched.append(sql)
            self.assertEqual(touched, [])
            self.assertEqual(before, self._snapshot(fresh))
