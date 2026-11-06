"""Real PostgreSQL source-lock contract for generated projections."""

from queue import Queue
from threading import Event, Thread
from time import monotonic
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase

from sources.waste_collection import derived_values
from sources.waste_collection.models import CollectionPropertyValue
from sources.waste_collection.tests import (
    test_generated_pipeline_numeric as numeric_contracts,
)


class GeneratedSourceLockTests(TransactionTestCase):
    _raw = numeric_contracts.GeneratedPipelineNumericalTests._raw
    _assert_output = numeric_contracts.GeneratedPipelineNumericalTests._assert_output

    def setUp(self):
        super().setUp()
        # Reuse exactly the synthetic numeric fixture without TestCase's outer
        # transaction, which would hide source rows from the worker connection.
        numeric_contracts.GeneratedPipelineNumericalTests.setUpTestData.__func__(
            type(self)
        )
        numeric_contracts.GeneratedPipelineNumericalTests.setUp(self)

    def test_waiter_reloads_the_locked_source_before_computing(self):
        source = self._raw(self.specific, self.specific_unit, "150")
        initial = self._assert_output(source, self.total, self.total_unit, "300")
        backend_ids = Queue()
        results = Queue()
        errors = Queue()
        finished = Event()
        computing = Event()
        compute = derived_values._compute_counterpart_value

        def observed_compute(locked_source):
            computing.set()
            return compute(locked_source)

        def work():
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '20s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_ids.put(cursor.fetchone()[0])
                generated, action = derived_values.create_or_update_derived_cpv(source)
                results.put((generated.pk, generated.average, action))
            except BaseException as exc:
                errors.put(exc)
            finally:
                connections["default"].close()
                finished.set()

        worker = Thread(target=work, daemon=True)
        with patch.object(
            derived_values, "_compute_counterpart_value", observed_compute
        ):
            try:
                with transaction.atomic():
                    CollectionPropertyValue.objects.select_for_update(no_key=True).get(
                        pk=source.pk
                    )
                    CollectionPropertyValue.objects.filter(pk=source.pk).update(
                        average=175
                    )
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        blocker_pid = cursor.fetchone()[0]
                    worker.start()
                    waiter_pid = backend_ids.get(timeout=10)
                    blocked_on_source = False
                    deadline = monotonic() + 10
                    while monotonic() < deadline:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [waiter_pid])
                            blockers = cursor.fetchone()[0]
                        if blocker_pid in blockers:
                            blocked_on_source = True
                            break
                        if finished.wait(0.01):
                            break
                    self.assertTrue(
                        blocked_on_source,
                        "worker never blocked on the held raw source row",
                    )
                    self.assertFalse(computing.is_set())
                    initial.refresh_from_db()
                    self.assertEqual(initial.average, 300)
            finally:
                if worker.ident is not None:
                    worker.join(timeout=30)
            self.assertFalse(worker.is_alive(), "generation worker did not finish")
        if not errors.empty():
            raise errors.get()
        self.assertEqual(results.get_nowait(), (initial.pk, 350, "updated"))
        source.refresh_from_db()
        initial.refresh_from_db()
        self.assertEqual(source.average, 175)
        self.assertEqual(initial.average, 350)
        self.assertEqual(initial.derived_from_id, source.pk)
