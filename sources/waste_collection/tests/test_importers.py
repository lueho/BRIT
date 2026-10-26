from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from queue import Queue
from threading import Event
from time import monotonic
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase

from bibliography.models import Source
from distributions.models import Period, TemporalDistribution, Timestep
from materials.models import Material, MaterialCategory
from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteFlyer,
)
from utils.object_management.models import ReviewAction
from utils.tests.testrunner import serial_test


@serial_test
class CollectionImporterConcurrencyTests(TransactionTestCase):
    _TEARDOWN_MODELS = (
        ReviewAction,
        Collection,
        WasteFlyer,
        Source,
        CollectionCountOptions,
        CollectionFrequency,
        Period,
        Collector,
        CollectionCatchment,
        CollectionSystem,
        WasteCategory,
        Timestep,
        TemporalDistribution,
        User,
    )

    def _fixture_teardown(self):
        """Delete the objects these tests created instead of flushing.

        The default TransactionTestCase teardown TRUNCATEs every table in the
        database, which costs ~60s per test on this stack. These tests only
        write a bounded set of objects, so removing the rows added since
        ``setUp`` restores the same isolation without the flush and keeps
        seeded reference data (``ensure_initial_data``) for later tests.
        """
        preexisting = getattr(self, "_preexisting_pks", None)
        if preexisting is None:
            return
        for model in self._TEARDOWN_MODELS:
            model.objects.exclude(pk__in=preexisting[model]).delete()

    def setUp(self):
        self._preexisting_pks = {
            model: set(model.objects.values_list("pk", flat=True))
            for model in self._TEARDOWN_MODELS
        }
        default_owner, _ = User.objects.get_or_create(
            username=settings.DEFAULT_OBJECT_OWNER_USERNAME
        )
        self.owner = User.objects.create_user(username="concurrent-importer")
        self.catchments = [
            CollectionCatchment.objects.create(name=f"Concurrent catchment {i}")
            for i in range(2)
        ]
        self.system = CollectionSystem.objects.create(name="Concurrent system")
        self.category = WasteCategory.objects.create(name="Concurrent category")
        months, _ = TemporalDistribution.objects.get_or_create(
            name="Months of the year", owner=default_owner
        )
        january, _ = Timestep.objects.get_or_create(
            name="January", owner=default_owner, defaults={"distribution": months}
        )
        december, _ = Timestep.objects.get_or_create(
            name="December", owner=default_owner, defaults={"distribution": months}
        )
        self.season, _ = CollectionSeason.objects.get_or_create(
            distribution=months, first_timestep=january, last_timestep=december
        )

    def _record(self, index, **references):
        return {
            "catchment_name": self.catchments[index].name,
            "collection_system": self.system.name,
            "waste_category": self.category.name,
            "valid_from": date(2099, 1, 1),
        } | references

    def _overlapping_imports(self, first_record, second_record, *, dry_run=False):
        importers = [
            CollectionImporter(owner=self.owner, create_collectors=True)
            for _ in range(2)
        ]
        for importer in importers:
            importer._load_lookups()

        first_created = Event()
        release_first = Event()
        second_pid = Queue()
        import_record = importers[0]._import_record

        def pause_before_commit(record, index, stats):
            import_record(record, index, stats)
            first_created.set()
            if not release_first.wait(10):
                raise TimeoutError("First importer was not released")

        def run(index, record):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    if index == 1:
                        cursor.execute("SELECT pg_backend_pid()")
                        second_pid.put(cursor.fetchone()[0])
                return importers[index].run([record], dry_run=dry_run and index == 0)
            finally:
                connections.close_all()

        with (
            patch.object(
                importers[0], "_import_record", side_effect=pause_before_commit
            ),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            first = executor.submit(run, 0, first_record)
            try:
                self.assertTrue(first_created.wait(10), "First import did not create")
                second = executor.submit(run, 1, second_record)
                pid = second_pid.get(timeout=10)
                deadline = monotonic() + 4
                while not second.done():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT EXISTS (SELECT 1 FROM pg_locks "
                            "WHERE pid = %s AND NOT granted)",
                            [pid],
                        )
                        waiting = cursor.fetchone()[0]
                    if waiting:
                        break
                    self.assertLess(monotonic(), deadline, "Second import did not run")
                    release_first.wait(0.01)
            finally:
                release_first.set()
            return first.result(timeout=10), second.result(timeout=10)

    def _assert_shared_reference(self, field):
        references = list(
            Collection.objects.filter(catchment__in=self.catchments)
            .order_by("pk")
            .values_list(f"{field}_id", flat=True)
        )
        self.assertEqual(len(references), 2)
        self.assertIsNotNone(references[0])
        self.assertEqual(references[0], references[1])

    def test_concurrent_collector_creation_by_name(self):
        records = [
            self._record(i, collector_name="Concurrent collector") for i in range(2)
        ]
        stats = self._overlapping_imports(*records)
        self.assertEqual(
            Collector.objects.filter(name="Concurrent collector").count(), 1
        )
        self.assertEqual(sum(s.get("collectors_created", 0) for s in stats), 1)
        self._assert_shared_reference("collector")

    def test_concurrent_collector_creation_by_website(self):
        website = "https://concurrent-collector.example.org"
        records = [self._record(i, collector_website=website) for i in range(2)]
        self._overlapping_imports(*records)
        self.assertEqual(Collector.objects.filter(website=website).count(), 1)
        self._assert_shared_reference("collector")

    def test_concurrent_fixed_frequency_creation(self):
        name = "Fixed; 177 per year"
        records = [self._record(i, frequency=name) for i in range(2)]
        self._overlapping_imports(*records)
        frequency = CollectionFrequency.objects.get(name=name)
        options = CollectionCountOptions.objects.get(frequency=frequency)
        self.assertEqual(options.standard, 177)
        self.assertEqual(options.season, self.season)
        self._assert_shared_reference("frequency")

    def test_concurrent_flexible_frequency_creation(self):
        name = "Fixed-Flexible; Standard: 178 per year; Optional: 179 per year"
        records = [self._record(i, frequency=name) for i in range(2)]
        self._overlapping_imports(*records)
        frequency = CollectionFrequency.objects.get(name=name)
        options = CollectionCountOptions.objects.get(frequency=frequency)
        self.assertEqual((options.standard, options.option_1), (178, 179))
        self.assertEqual(options.season, self.season)
        self._assert_shared_reference("frequency")

    def test_waiting_import_refreshes_normalized_collector_lookup(self):
        self._overlapping_imports(
            self._record(0, collector_name="Concurrent collector"),
            self._record(1, collector_name="CONCURRENT  COLLECTOR"),
        )
        self.assertEqual(Collector.objects.filter(owner=self.owner).count(), 1)
        self._assert_shared_reference("collector")

    def test_dry_run_releases_lock_and_waiting_import_creates_reference(self):
        name = "Dry run concurrent collector"
        records = [self._record(i, collector_name=name) for i in range(2)]
        stats = self._overlapping_imports(*records, dry_run=True)
        self.assertEqual([s["collectors_created"] for s in stats], [1, 1])
        self.assertEqual(Collector.objects.filter(name=name).count(), 1)
        self.assertEqual(
            Collection.objects.filter(catchment__in=self.catchments).count(), 1
        )


class ImporterTeardownScopeTests(TestCase):
    """The concurrency tests replace the default full-database flush with a
    targeted teardown. It must remove the objects those tests create while
    leaving unrelated rows untouched — the full flush costs ~60s per test on
    this stack for no benefit."""

    def test_fixture_teardown_preserves_unrelated_rows(self):
        marker = MaterialCategory.objects.create(name="Teardown scope marker")
        case = CollectionImporterConcurrencyTests(
            "test_concurrent_collector_creation_by_name"
        )
        case._fixture_teardown()
        self.assertTrue(MaterialCategory.objects.filter(pk=marker.pk).exists())

    def test_fixture_teardown_preserves_rows_that_existed_before_the_test(self):
        """Seeded reference data (e.g. ensure_initial_data distributions) must
        survive for later serial tests."""
        seeded_user = User.objects.create(username="seeded-before-test")
        seeded = TemporalDistribution.objects.create(
            name="Seeded distribution", owner=seeded_user
        )
        case = CollectionImporterConcurrencyTests(
            "test_concurrent_collector_creation_by_name"
        )
        case.setUp()
        case._fixture_teardown()
        self.assertTrue(TemporalDistribution.objects.filter(pk=seeded.pk).exists())
        self.assertTrue(User.objects.filter(pk=seeded_user.pk).exists())

    def test_fixture_teardown_removes_objects_the_tests_create(self):
        case = CollectionImporterConcurrencyTests(
            "test_concurrent_collector_creation_by_name"
        )
        case.setUp()
        case._fixture_teardown()
        self.assertFalse(
            CollectionCatchment.objects.filter(
                name__startswith="Concurrent catchment"
            ).exists()
        )
        self.assertFalse(
            CollectionSystem.objects.filter(name="Concurrent system").exists()
        )
        self.assertFalse(
            WasteCategory.objects.filter(name="Concurrent category").exists()
        )
        self.assertFalse(User.objects.filter(username="concurrent-importer").exists())
        for model, pks in case._preexisting_pks.items():
            with self.subTest(model=model.__name__):
                self.assertSetEqual(
                    set(model.objects.values_list("pk", flat=True)), pks
                )


class CollectionImporterRecordTests(TestCase):
    """Characterization tests for the single-record import pipeline."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="importer-record-owner")
        cls.catchment = CollectionCatchment.objects.create(name="Record Catchment")
        cls.system = CollectionSystem.objects.create(name="Record System")
        cls.other_system = CollectionSystem.objects.create(name="Other Record System")
        cls.category = WasteCategory.objects.create(name="Record Category")
        cls.allowed_material = Material.objects.create(
            name="Record Allowed Material", owner=cls.owner
        )
        cls.forbidden_material = Material.objects.create(
            name="Record Forbidden Material", owner=cls.owner
        )
        cls.valid_from = date(2099, 6, 1)

    def _record(self, **overrides):
        record = {
            "catchment_name": self.catchment.name,
            "collection_system": self.system.name,
            "waste_category": self.category.name,
            "valid_from": self.valid_from,
            "sources": [],
            "flyer_urls": [],
            "property_values": [],
        }
        record.update(overrides)
        return record

    def _import(self, *records, **kwargs):
        importer = CollectionImporter(owner=self.owner, **kwargs)
        return importer.run(list(records))

    def _collection(self, **filters):
        return Collection.objects.get(catchment=self.catchment, **filters)

    def test_repeated_identical_import_counts_unchanged(self):
        stats = self._import(self._record())
        self.assertEqual(stats["created"], 1)

        stats = self._import(self._record())

        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats.get("updated", 0), 0)
        self.assertEqual(Collection.objects.filter(catchment=self.catchment).count(), 1)

    def test_existing_collection_update_reports_changes(self):
        self._import(self._record())
        frequency = CollectionFrequency.objects.create(name="Record weekly")

        stats = self._import(
            self._record(frequency=frequency.name, description="Updated")
        )

        self.assertEqual(stats.get("updated"), 1)
        collection = self._collection()
        self.assertEqual(collection.frequency, frequency)
        self.assertEqual(collection.description, "Updated")

    def test_same_year_reconcile_updates_distinct_system_collection(self):
        self._import(self._record())

        stats = self._import(
            self._record(
                collection_system=self.other_system.name,
                reconcile_same_year_identity=True,
            )
        )

        self.assertEqual(stats.get("updated"), 1)
        self.assertEqual(Collection.objects.filter(catchment=self.catchment).count(), 1)
        self.assertEqual(self._collection().collection_system, self.other_system)

    def test_distinct_system_without_reconcile_creates_second_collection(self):
        self._import(self._record())

        stats = self._import(self._record(collection_system=self.other_system.name))

        self.assertEqual(stats["created"], 1)
        self.assertEqual(Collection.objects.filter(catchment=self.catchment).count(), 2)

    def test_omitted_frequency_keeps_value_but_clear_frequency_removes_it(self):
        frequency = CollectionFrequency.objects.create(name="Record weekly")
        self._import(self._record(frequency=frequency.name))
        self.assertEqual(self._collection().frequency, frequency)

        self._import(self._record(description="Touched"))
        self.assertEqual(self._collection().frequency, frequency)

        self._import(self._record(clear_frequency=True))
        self.assertIsNone(self._collection().frequency)

    def test_different_material_lists_create_separate_collection(self):
        self._import(self._record(allowed_materials=self.allowed_material.name))

        stats = self._import(
            self._record(
                allowed_materials=self.forbidden_material.name,
                forbidden_materials=self.allowed_material.name,
            )
        )

        self.assertEqual(stats["created"], 1)
        self.assertEqual(Collection.objects.filter(catchment=self.catchment).count(), 2)

    def test_identical_material_lists_survive_update(self):
        self._import(
            self._record(
                allowed_materials=self.allowed_material.name,
                forbidden_materials=self.forbidden_material.name,
            )
        )

        stats = self._import(
            self._record(
                allowed_materials=self.allowed_material.name,
                forbidden_materials=self.forbidden_material.name,
                description="Touched",
            )
        )

        self.assertEqual(stats.get("updated"), 1)
        collection = self._collection()
        self.assertEqual(
            list(collection.allowed_materials.all()), [self.allowed_material]
        )
        self.assertEqual(
            list(collection.forbidden_materials.all()), [self.forbidden_material]
        )

    def test_predecessor_is_linked_and_valid_until_updated(self):
        previous_valid_from = date(2098, 1, 1)
        self._import(self._record(valid_from=previous_valid_from))
        predecessor = self._collection(valid_from=previous_valid_from)
        self.assertIsNone(predecessor.valid_until)

        stats = self._import(self._record())

        self.assertEqual(stats["predecessor_links"], 1)
        predecessor.refresh_from_db()
        self.assertEqual(predecessor.valid_until, self.valid_from - timedelta(days=1))
        collection = self._collection(valid_from=self.valid_from)
        self.assertIn(predecessor, collection.predecessors.all())

    def test_update_path_syncs_sources_and_review_comment(self):
        self._import(self._record(sources=["Source A"], review_comment="first"))
        collection = self._collection()
        self.assertEqual({s.title for s in collection.sources.all()}, {"Source A"})

        stats = self._import(
            self._record(sources=["Source B"], review_comment="second")
        )

        self.assertEqual(stats.get("updated"), 1)
        self.assertEqual({s.title for s in collection.sources.all()}, {"Source B"})
        comment = ReviewAction.for_object(collection).get(
            action=ReviewAction.ACTION_COMMENT,
            user=self.owner,
        )
        self.assertIn("second", comment.comment)

    def test_review_comment_only_change_is_not_counted_as_update(self):
        self._import(self._record(review_comment="first"))

        stats = self._import(self._record(review_comment="second"))

        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats["review_comments_created"], 1)
        comment = ReviewAction.for_object(self._collection()).get(
            action=ReviewAction.ACTION_COMMENT,
            user=self.owner,
        )
        self.assertIn("second", comment.comment)
