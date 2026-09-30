from concurrent.futures import ThreadPoolExecutor
from datetime import date
from queue import Queue
from threading import Event
from time import monotonic
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TransactionTestCase

from distributions.models import TemporalDistribution, Timestep
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
)


class CollectionImporterConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
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
