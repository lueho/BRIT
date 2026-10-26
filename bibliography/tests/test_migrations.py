import uuid
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import connection, migrations
from django.db.migrations.exceptions import InconsistentMigrationHistory
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from utils.tests.testrunner import serial_test

APP_LABEL = "bibliography"
SQUASHED_KEY = (APP_LABEL, "0001_squashed_0012")
OBSOLETE_MIGRATIONS = [
    "0001_initial",
    "0002_author_approved_at_author_approved_by_and_more",
    "0003_alter_author_publication_status_and_more",
    "0004_alter_author_publication_status_and_more",
    "0005_alter_source_abbreviation_blank",
    "0006_alter_source_url",
    "0007_source_article_metadata",
    "0008_source_article_number",
    "0009_rename_source_bibtex_fields",
    "0010_author_contact_details",
    "0011_author_author_type_author_organization_abbreviation_and_more",
    "0012_source_type_vocabulary",
]
BIBLIOGRAPHY_TABLES = (
    "bibliography_author",
    "bibliography_licence",
    "bibliography_source",
    "bibliography_sourceauthor",
)
MIGRATION_TEST_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "bibliography",
]


class FinalizedBaselineGraphTests(SimpleTestCase):
    """Static checks on the finalized baseline migration; no database needed."""

    def test_full_graph_validates_without_missing_nodes_or_cycles(self):
        loader = MigrationLoader(None)
        loader.graph.validate_consistency()
        loader.graph.ensure_not_cyclic()

    def test_disk_migrations_are_exactly_the_baseline(self):
        loader = MigrationLoader(None)
        bibliography_keys = [
            key for key in loader.disk_migrations if key[0] == APP_LABEL
        ]
        self.assertEqual(bibliography_keys, [SQUASHED_KEY])
        migration = loader.disk_migrations[SQUASHED_KEY]
        self.assertTrue(migration.initial)
        self.assertEqual(
            migration.replaces,
            [(APP_LABEL, name) for name in OBSOLETE_MIGRATIONS],
        )
        self.assertEqual(
            migration.dependencies,
            [migrations.swappable_dependency(settings.AUTH_USER_MODEL)],
        )
        for name in OBSOLETE_MIGRATIONS:
            self.assertNotIn((APP_LABEL, name), loader.disk_migrations)

    def test_surviving_dependencies_point_to_baseline(self):
        loader = MigrationLoader(None)
        offenders = []
        for key, migration in loader.disk_migrations.items():
            for dependency in migration.dependencies:
                if dependency[0] == APP_LABEL and tuple(dependency) != SQUASHED_KEY:
                    offenders.append((key, dependency))
        self.assertEqual(offenders, [])

    def test_replacement_operations_are_schema_only(self):
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[SQUASHED_KEY]
        self.assertTrue(migration.operations)
        for operation in migration.operations:
            self.assertNotIsInstance(
                operation, (migrations.RunPython, migrations.RunSQL)
            )

    def test_replacement_operations_build_final_schema_directly(self):
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[SQUASHED_KEY]
        creates = [
            op for op in migration.operations if isinstance(op, migrations.CreateModel)
        ]
        self.assertEqual(
            [op.name for op in creates],
            ["Author", "Licence", "Source", "SourceAuthor"],
        )
        remaining = [
            op
            for op in migration.operations
            if not isinstance(op, migrations.CreateModel)
        ]
        self.assertEqual(len(remaining), 1)
        self.assertIsInstance(remaining[0], migrations.AddField)
        self.assertEqual(remaining[0].model_name, "source")
        self.assertEqual(remaining[0].name, "authors")

    def test_fresh_plan_contains_only_the_baseline(self):
        loader = MigrationLoader(None)
        self.assertEqual(loader.graph.leaf_nodes(APP_LABEL), [SQUASHED_KEY])
        plan = [
            node
            for node in loader.graph.forwards_plan(SQUASHED_KEY)
            if node[0] == APP_LABEL
        ]
        self.assertEqual(plan, [SQUASHED_KEY])

    def test_migrated_state_matches_current_models(self):
        loader = MigrationLoader(None)
        migrated_state = loader.project_state()
        current_state = ProjectState.from_apps(apps)
        migrated = {
            key: state
            for key, state in migrated_state.models.items()
            if key[0] == APP_LABEL
        }
        current = {
            key: state
            for key, state in current_state.models.items()
            if key[0] == APP_LABEL
        }
        self.assertEqual(sorted(migrated), sorted(current))
        for key, migrated_model_state in migrated.items():
            self.assertEqual(current[key], migrated_model_state, key)

    def test_adopted_history_with_obsolete_records_stays_consistent(self):
        disk_loader = MigrationLoader(None)
        applied = set(disk_loader.disk_migrations) | {
            (APP_LABEL, name) for name in OBSOLETE_MIGRATIONS
        }
        applied.add(SQUASHED_KEY)
        with mock.patch.object(
            MigrationRecorder,
            "applied_migrations",
            side_effect=lambda: dict.fromkeys(applied),
        ):
            loader = MigrationLoader(connection)
            loader.check_consistent_history(connection)

    def test_original_history_without_baseline_is_adopted(self):
        disk_loader = MigrationLoader(None)
        applied = set(disk_loader.disk_migrations) | {
            (APP_LABEL, name) for name in OBSOLETE_MIGRATIONS
        }
        applied.discard(SQUASHED_KEY)
        with mock.patch.object(
            MigrationRecorder,
            "applied_migrations",
            side_effect=lambda: dict.fromkeys(applied),
        ):
            loader = MigrationLoader(connection)
            loader.check_consistent_history(connection)
        self.assertIn(SQUASHED_KEY, loader.applied_migrations)

    def test_missing_baseline_and_originals_breaks_dependents(self):
        disk_loader = MigrationLoader(None)
        applied = set(disk_loader.disk_migrations)
        applied.discard(SQUASHED_KEY)
        with mock.patch.object(
            MigrationRecorder,
            "applied_migrations",
            side_effect=lambda: dict.fromkeys(applied),
        ):
            loader = MigrationLoader(connection)
            with self.assertRaises(InconsistentMigrationHistory) as context:
                loader.check_consistent_history(connection)
        self.assertIn(SQUASHED_KEY[1], str(context.exception))


@serial_test
class FinalizedBaselineRuntimeTests(SimpleTestCase):
    """Migrate real PostgreSQL schemas inside the disposable test database.

    Each test creates a uniquely named scratch schema and restricts the
    session search_path to it, so migration bookkeeping and created tables
    stay isolated from the public schema.
    """

    databases = {"default"}

    def _scratch_schema(self):
        schema = f"migtest_{uuid.uuid4().hex[:16]}"
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path")
            original_search_path = cursor.fetchone()[0]
            cursor.execute(f'CREATE SCHEMA "{schema}"')

        def cleanup():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('search_path', %s, false)",
                    [original_search_path],
                )
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

        self.addCleanup(cleanup)
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        return schema

    def _executor(self):
        return MigrationExecutor(connection)

    def _tables(self, schema):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s",
                [schema],
            )
            return {row[0] for row in cursor.fetchall()}

    def _columns(self, schema, table):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s",
                [schema, table],
            )
            return {row[0] for row in cursor.fetchall()}

    def _row_count(self, schema, table):
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            return cursor.fetchone()[0]

    def _snapshot(self, schema):
        snapshot = {}
        for table in (*BIBLIOGRAPHY_TABLES, "auth_user"):
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT * FROM "{schema}"."{table}" ORDER BY id')
                names = [col.name for col in cursor.description]
                snapshot[table] = [
                    dict(zip(names, row, strict=True)) for row in cursor.fetchall()
                ]
        return snapshot

    def _applied(self):
        return set(MigrationRecorder(connection).applied_migrations())

    def _create_owner(self, apps):
        User = apps.get_model("auth", "User")
        return User.objects.create(
            username="squash-test-owner",
            password=make_password("Squash-Test-Passw0rd"),
        )

    def _create_current_fixtures(self, apps, owner):
        Licence = apps.get_model("bibliography", "Licence")
        Author = apps.get_model("bibliography", "Author")
        Source = apps.get_model("bibliography", "Source")
        SourceAuthor = apps.get_model("bibliography", "SourceAuthor")
        licence = Licence.objects.create(
            name="Test Licence",
            description="licence description",
            reference_url="https://example.org/licence",
            publication_status="published",
            owner_id=owner.pk,
        )
        author = Author.objects.create(
            author_type="person",
            last_names="Zed",
            first_names="Anna",
            institution="Test Institute",
            contact_email="anna@example.org",
            publication_status="published",
            owner_id=owner.pk,
        )
        source = Source.objects.create(
            type="article",
            title="Tip Source",
            citation_key="TIPKEY",
            number="7",
            eid="tip-eid-1",
            journal="Journal of Tests",
            year=2024,
            month="may",
            pages="1-9",
            volume="12",
            doi="10.1234/tip",
            url="https://example.org/tip",
            url_valid=True,
            abstract="tip abstract",
            attributions="tip attributions",
            publication_status="published",
            owner_id=owner.pk,
            licence_id=licence.pk,
            created_by_id=owner.pk,
            lastmodified_by_id=owner.pk,
        )
        SourceAuthor.objects.create(
            source_id=source.pk, author_id=author.pk, position=3
        )

    @override_settings(INSTALLED_APPS=MIGRATION_TEST_APPS)
    def test_fresh_database_applies_baseline_schema(self):
        schema = self._scratch_schema()
        executor = self._executor()
        leaf = executor.loader.graph.leaf_nodes(APP_LABEL)[0]
        self.assertEqual(leaf, SQUASHED_KEY)
        executor.migrate([leaf])
        self.assertTrue(set(BIBLIOGRAPHY_TABLES).issubset(self._tables(schema)))
        for table in BIBLIOGRAPHY_TABLES:
            self.assertEqual(self._row_count(schema, table), 0, table)
        self.assertEqual(self._row_count(schema, "auth_user"), 0)
        self.assertIn(SQUASHED_KEY, self._applied())

        apps = executor.loader.project_state(nodes=[leaf]).apps
        Source = apps.get_model("bibliography", "Source")
        type_field = Source._meta.get_field("type")
        self.assertEqual(type_field.default, "misc")
        choice_keys = {key for key, _label in type_field.choices}
        self.assertIn("online", choice_keys)
        self.assertIn("misc", choice_keys)
        self.assertNotIn("website", choice_keys)
        self.assertNotIn("custom", choice_keys)
        columns = self._columns(schema, "bibliography_source")
        self.assertTrue({"citation_key", "number", "eid"}.issubset(columns))
        self.assertFalse({"abbreviation", "issue", "article_number"} & columns)

    @override_settings(INSTALLED_APPS=MIGRATION_TEST_APPS)
    def test_migrate_records_baseline_for_original_history(self):
        schema = self._scratch_schema()
        executor = self._executor()
        executor.migrate([SQUASHED_KEY])
        apps = executor.loader.project_state(nodes=[SQUASHED_KEY]).apps
        owner = self._create_owner(apps)
        self._create_current_fixtures(apps, owner)

        recorder = MigrationRecorder(connection)
        recorder.record_unapplied(*SQUASHED_KEY)
        for name in OBSOLETE_MIGRATIONS:
            recorder.record_applied(APP_LABEL, name)
        before = self._snapshot(schema)
        self.assertNotIn(SQUASHED_KEY, self._applied())

        executor = self._executor()
        executor.loader.check_consistent_history(connection)
        with CaptureQueriesContext(connection) as captured:
            executor.migrate([SQUASHED_KEY])
        bibliography_sql = [
            query["sql"]
            for query in captured.captured_queries
            if '"bibliography_' in query["sql"]
        ]
        self.assertEqual(bibliography_sql, [])
        self.assertEqual(before, self._snapshot(schema))
        applied = self._applied()
        self.assertIn(SQUASHED_KEY, applied)
        for name in OBSOLETE_MIGRATIONS:
            self.assertIn((APP_LABEL, name), applied)

    @override_settings(INSTALLED_APPS=MIGRATION_TEST_APPS)
    def test_adopted_history_keeps_data_and_records_stable(self):
        schema = self._scratch_schema()
        executor = self._executor()
        executor.migrate([SQUASHED_KEY])
        apps = executor.loader.project_state(nodes=[SQUASHED_KEY]).apps
        owner = self._create_owner(apps)
        self._create_current_fixtures(apps, owner)

        recorder = MigrationRecorder(connection)
        for name in OBSOLETE_MIGRATIONS:
            recorder.record_applied(APP_LABEL, name)
        before = self._snapshot(schema)
        applied_before = self._applied()

        executor = self._executor()
        executor.loader.check_consistent_history(connection)
        pending = [
            migration.name
            for migration, backwards in executor.migration_plan([SQUASHED_KEY])
            if migration.app_label == APP_LABEL and not backwards
        ]
        self.assertEqual(pending, [])
        with CaptureQueriesContext(connection) as captured:
            executor.migrate([SQUASHED_KEY])
            executor.migrate([SQUASHED_KEY])
        bibliography_sql = [
            query["sql"]
            for query in captured.captured_queries
            if '"bibliography_' in query["sql"]
        ]
        self.assertEqual(bibliography_sql, [])
        self.assertEqual(before, self._snapshot(schema))
        self.assertEqual(applied_before, self._applied())
