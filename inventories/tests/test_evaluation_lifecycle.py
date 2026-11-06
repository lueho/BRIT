"""Run-generation (`run_id`) lifecycle: fences, invalidation, settlement."""

import uuid
from unittest.mock import MagicMock, patch

from celery import states
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Polygon
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventories import tasks
from inventories.exceptions import BlockedRunningScenario
from inventories.models import (
    InventoryAlgorithm,
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
    is_current_inventory_run,
    locked_scenario_evaluation,
)
from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, SampleSeries
from utils.object_management.models import ReviewAction
from utils.object_management.services import content_mutation

User = get_user_model()
RUN_ID = uuid.uuid4()
OTHER_RUN_ID = uuid.uuid4()


def _events_for(scenario):
    return ReviewAction.objects.filter(
        content_type__app_label="inventories",
        content_type__model="scenario",
        object_id=scenario.pk,
    )


def _backend(state):
    def fake(uuid_arg):
        m = MagicMock()
        m.state = state
        return m

    return fake


class LifecycleFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="lc-owner")
        cls.region = Region.objects.create(name="lc-region", country="DE")
        cls.catchment = Catchment.objects.create(
            name="lc-catch", region=cls.region, parent_region=cls.region
        )
        cls.material = Material.objects.create(name="lc-mat")
        cls.series = SampleSeries.objects.create(name="lc-ss", material=cls.material)
        cls.geo = GeoDataset.objects.create(name="lc-geo", region=cls.region)
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="lc-algo",
            source_module="inventories.algorithms",
            function_name="lc_fn",
            geodataset=cls.geo,
        )
        cls.scenario = Scenario.objects.create(
            name="lc-sc", region=cls.region, catchment=cls.catchment, owner=cls.owner
        )
        cls.config = ScenarioInventoryConfiguration.objects.create(
            scenario=cls.scenario,
            feedstock=cls.material,
            geodataset=cls.geo,
            inventory_algorithm=cls.algorithm,
            sample_series=cls.series,
        )

    def _status(self):
        return ScenarioStatus.objects.get(scenario=self.scenario)

    def _snapshot(self):
        return {
            "scenario": Scenario.objects.filter(pk=self.scenario.pk).values().get(),
            "status": ScenarioStatus.objects.filter(scenario=self.scenario)
            .values()
            .get(),
            "configs": list(
                ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario)
                .order_by("pk")
                .values()
            ),
            "tasks": list(
                RunningTask.objects.filter(scenario=self.scenario)
                .order_by("pk")
                .values()
            ),
            "layers": list(
                Layer.all_objects.filter(scenario=self.scenario).order_by("pk").values()
            ),
            "layer_fields": list(
                Layer.layer_fields.through.objects.filter(layer__scenario=self.scenario)
                .order_by("pk")
                .values()
            ),
            "audits": list(_events_for(self.scenario).order_by("pk").values()),
        }

    def _start_attempt(self, run_id=RUN_ID):
        status = self._status()
        status.status = ScenarioStatus.Status.RUNNING
        status.run_id = run_id
        status.failed_algorithm = None
        status.failure_message = ""
        status.save()
        return status

    def _make_failed(self, run_id=RUN_ID):
        st = self._status()
        st.status = ScenarioStatus.Status.FAILED
        st.failed_algorithm = self.algorithm
        st.failure_message = "algo boom"
        st.run_id = run_id
        st.save()
        rt = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=run_id,
        )
        return st, rt

    def _layer(self, *, run_id=None, staged=False, table_name="lc_live_tbl"):
        return Layer.all_objects.create(
            name="lc-layer",
            scenario=self.scenario,
            algorithm=self.algorithm,
            feedstock=self.material,
            staged=staged,
            table_name=table_name,
            geom_type="Polygon",
            run_id=run_id,
        )

    def _staged_layer(self, run_id=RUN_ID):
        return self._layer(run_id=run_id, staged=True, table_name="lc_tbl")


class ConfigInvalidationTestCase(LifecycleFixtures, TestCase):
    """A: config delete/save invalidates quiescent state; blocks on active work."""

    def test_config_delete_from_failed_invalidates_to_changed(self):
        st, rt = self._make_failed()
        staged = self._staged_layer()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            self.config.delete()
        self.assertFalse(Layer.all_objects.filter(pk=staged.pk).exists())
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(st.failed_algorithm_id)
        self.assertEqual(st.failure_message, "")
        self.assertIsNone(st.run_id)
        self.assertFalse(RunningTask.objects.filter(pk=rt.pk).exists())
        self.assertFalse(Layer.all_objects.filter(pk=staged.pk).exists())

    def test_scenario_input_edit_from_failed_cleans_state(self):
        st, rt = self._make_failed()
        self._staged_layer()
        live = self._layer()
        self.scenario.refresh_from_db()
        self.assertEqual(
            self.scenario.scenariostatus.status, ScenarioStatus.Status.FAILED
        )
        self.scenario.catchment = None
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            self.scenario.save(update_fields=["catchment"])
        self.assertEqual(
            self.scenario.scenariostatus.status, ScenarioStatus.Status.CHANGED
        )
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(st.run_id)
        self.assertIsNone(st.failed_algorithm_id)
        self.assertEqual(st.failure_message, "")
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        self.assertFalse(
            Layer.all_objects.filter(scenario=self.scenario, staged=True).exists()
        )
        self.assertTrue(Layer.objects.filter(pk=live.pk).exists())
        self.scenario.refresh_from_db()
        self.assertIsNone(self.scenario.catchment_id)

    def test_missing_status_row_blocks_input_save(self):
        st, rt = self._make_failed()
        before = Scenario.objects.filter(pk=self.scenario.pk).values().get()
        st.delete()
        self.scenario.catchment = None
        with self.assertRaises(BlockedRunningScenario):
            self.scenario.save(update_fields=["catchment"])
        self.assertEqual(
            Scenario.objects.filter(pk=self.scenario.pk).values().get(), before
        )
        self.assertFalse(ScenarioStatus.objects.filter(scenario=self.scenario).exists())

    def test_config_queryset_delete_invalidates(self):
        st, rt = self._make_failed()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).delete()
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(st.run_id)

    def test_metadata_only_scenario_save_keeps_failed(self):
        st, rt = self._make_failed()
        before = self._snapshot()
        before_root = before.pop("scenario")
        self.scenario.name = "lc-renamed"
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            self.scenario.save(update_fields=["name"])
        after = self._snapshot()
        after_root = after.pop("scenario")
        self.assertEqual(after, before)
        self.assertEqual(after_root["name"], "lc-renamed")
        self.assertEqual(
            after_root["content_revision"], before_root["content_revision"]
        )
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FAILED)

    def test_config_save_blocked_on_active_running_task(self):
        st, rt = self._make_failed()
        before = self._snapshot()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.STARTED)
        ):
            with transaction.atomic():
                with self.assertRaises(BlockedRunningScenario):
                    ScenarioInventoryConfiguration.objects.create(
                        scenario=self.scenario,
                        feedstock=self.material,
                        geodataset=self.geo,
                        inventory_algorithm=self.algorithm,
                    )
        self.assertEqual(self._snapshot(), before)

    def test_config_delete_blocked_on_active_task_keeps_state(self):
        st, rt = self._make_failed()
        self._staged_layer()
        before = self._snapshot()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.STARTED)
        ):
            with transaction.atomic():
                with self.assertRaises(BlockedRunningScenario):
                    self.config.delete()
        self.assertEqual(self._snapshot(), before)
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FAILED)

    def test_failed_config_save_does_not_invalidate_previous_state(self):
        self._make_failed()
        self._staged_layer()
        before = self._snapshot()
        self.config.geodataset = None
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            with self.assertRaises(IntegrityError):
                self.config.save(update_fields=["geodataset"])
        self.assertEqual(self._snapshot(), before)

    def test_missing_status_blocks_configuration_mutation(self):
        self._status().delete()
        with self.assertRaises(BlockedRunningScenario):
            self.config.save()
        with self.assertRaises(BlockedRunningScenario):
            with transaction.atomic():
                self.config.delete()
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertFalse(ScenarioStatus.objects.filter(scenario=self.scenario).exists())

    def test_active_work_blocks_scenario_save_after_other_invalidation(self):
        status, _ = self._make_failed()
        status.status = ScenarioStatus.Status.CHANGED
        status.run_id = None
        status.save()
        before = self._snapshot()
        self.scenario.name = "must-not-persist"
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.PENDING)
        ):
            with self.assertRaises(BlockedRunningScenario):
                self.scenario.save(update_fields=["name"])
        self.assertEqual(self._snapshot(), before)

    def test_stale_running_recovery_clears_identity_diagnostics_and_staging(self):
        status, _ = self._make_failed()
        status.status = ScenarioStatus.Status.RUNNING
        status.save()
        self._staged_layer()
        self.scenario.name = "recovered"
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.FAILURE)
        ):
            self.scenario.save(update_fields=["name"])
        status.refresh_from_db()
        self.assertEqual(status.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(status.run_id)
        self.assertIsNone(status.failed_algorithm_id)
        self.assertEqual(status.failure_message, "")
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        self.assertFalse(
            Layer.all_objects.filter(scenario=self.scenario, staged=True).exists()
        )

    def test_failed_scenario_update_rolls_back_stale_recovery(self):
        status, _ = self._make_failed()
        status.status = ScenarioStatus.Status.RUNNING
        status.save()
        self._staged_layer()
        before = self._snapshot()
        self.scenario.name = None
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.FAILURE)
        ):
            with self.assertRaises(IntegrityError):
                self.scenario.save(update_fields=["name"])
        self.assertEqual(self._snapshot(), before)

    def test_scenario_write_locks_root_before_status_and_task_rows(self):
        self._make_failed()
        self.scenario.name = "lock-order"
        with (
            patch(
                "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
            ),
            CaptureQueriesContext(connection) as queries,
        ):
            self.scenario.save(update_fields=["name"])
        locks = [q["sql"] for q in queries if "FOR UPDATE" in q["sql"]]
        self.assertGreaterEqual(len(locks), 3)
        for query, model in zip(
            locks[:3], (Scenario, ScenarioStatus, RunningTask), strict=True
        ):
            self.assertIn(f'FROM "{model._meta.db_table}"', query)


class HTTPConflictBoundaryTestCase(LifecycleFixtures, TestCase):
    """B: HTTP remove on settled FAILED works; active work -> 409; unauthorized 403."""

    def _client_owner(self):
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )
        c = Client()
        c.force_login(self.owner)
        return c

    def test_content_mutation_edit_from_failed_invalidates(self):
        st, rt = self._make_failed()
        self._staged_layer()
        live = self._layer()
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )
        revision = self.scenario.content_revision
        with (
            patch(
                "inventories.models.AsyncResult",
                side_effect=_backend(states.SUCCESS),
            ),
            content_mutation(self.owner, self.scenario, action="edit") as locked,
        ):
            self.assertEqual(locked.scenariostatus.status, ScenarioStatus.Status.FAILED)
            locked.catchment = None
            locked.save(update_fields=["catchment"])
            self.assertEqual(
                locked.scenariostatus.status, ScenarioStatus.Status.CHANGED
            )
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.CHANGED)
        self.assertIsNone(st.run_id)
        self.assertIsNone(st.failed_algorithm_id)
        self.assertEqual(st.failure_message, "")
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        self.assertFalse(
            Layer.all_objects.filter(scenario=self.scenario, staged=True).exists()
        )
        self.assertTrue(Layer.objects.filter(pk=live.pk).exists())
        self.scenario.refresh_from_db()
        self.assertIsNone(self.scenario.catchment_id)
        self.assertEqual(self.scenario.content_revision, revision + 1)
        events = list(_events_for(self.scenario))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, ReviewAction.ACTION_EDITED)
        self.assertEqual(events[0].user_id, self.owner.pk)
        self.assertEqual(events[0].content_revision, revision + 1)

    def test_remove_settled_failed_302_one_audit(self):
        st, rt = self._make_failed()
        client = self._client_owner()
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.material.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        revision = self.scenario.content_revision
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            resp = client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.content_revision, revision + 1)
        events = list(_events_for(self.scenario))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, ReviewAction.ACTION_EDITED)
        self.assertEqual(events[0].user_id, self.owner.pk)
        self.assertEqual(events[0].content_revision, revision + 1)

    def test_remove_active_task_409(self):
        st, rt = self._make_failed()
        client = self._client_owner()
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.material.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        before = self._snapshot()
        with (
            self.assertLogs("django.request", level="WARNING") as logs,
            patch(
                "inventories.models.AsyncResult", side_effect=_backend(states.STARTED)
            ),
        ):
            resp = client.post(url)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Conflict", "\n".join(logs.output))
        self.assertEqual(self._snapshot(), before)

    def test_foreign_actor_denial_preserves_complete_failed_state(self):
        self._make_failed()
        self._staged_layer()
        foreign = User.objects.create_user(username="lc-foreign")
        foreign.user_permissions.add(Permission.objects.get(codename="change_scenario"))
        client = Client()
        client.force_login(foreign)
        before = self._snapshot()
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.material.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        with self.assertLogs("django.request", level="WARNING") as logs:
            response = client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", "\n".join(logs.output))
        self.assertEqual(self._snapshot(), before)


class StartRunTestCase(LifecycleFixtures, TestCase):
    """C: start allocates a run_id, claims, enqueues; duplicates/stale no-op."""

    def test_start_allocates_uuid_and_enqueues(self):
        st = self._status()
        dispatched = []
        with patch("inventories.tasks.run_inventory.delay") as delay:
            delay.side_effect = lambda *a, **kw: dispatched.append((a, kw))
            with self.captureOnCommitCallbacks(execute=True) as _:
                ok = tasks.start_inventory_run(self.scenario.pk)
        self.assertTrue(ok)
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.RUNNING)
        self.assertIsNotNone(st.run_id)
        self.assertEqual(str(st.run_id), str(dispatched[0][0][1]))

    def test_start_rejected_while_active_task(self):
        st, rt = self._make_failed()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.STARTED)
        ):
            ok = tasks.start_inventory_run(self.scenario.pk)
        self.assertFalse(ok)
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(st.run_id, RUN_ID)

    def test_duplicate_worker_launch_same_run_noop(self):
        st, rt = self._make_failed()
        with (
            patch("inventories.tasks.chord") as chord_m,
            patch(
                "inventories.models.AsyncResult", side_effect=_backend(states.STARTED)
            ),
        ):
            result = tasks.run_inventory.run(self.scenario.pk, str(RUN_ID))
        self.assertIsNone(result)
        chord_m.assert_not_called()

    def test_stale_run_id_noop_everywhere(self):
        st, rt = self._make_failed()
        staged = self._staged_layer()
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(OTHER_RUN_ID), self.algorithm.pk, "stale msg"
        )
        st.refresh_from_db()
        self.assertEqual(st.failed_algorithm_id, self.algorithm.pk)  # unchanged
        tasks.finalize_inventory.run([True], self.scenario.pk, str(OTHER_RUN_ID))
        self.assertTrue(Layer.all_objects.filter(pk=staged.pk).exists())
        self.assertTrue(RunningTask.objects.filter(pk=rt.pk).exists())

    def test_rejected_retry_does_not_delete_settled_markers(self):
        _, header = self._make_failed()
        callback = RunningTask.objects.create(
            scenario=self.scenario, uuid=uuid.uuid4(), run_id=RUN_ID
        )
        legacy = RunningTask.objects.create(scenario=self.scenario, uuid=uuid.uuid4())
        self._staged_layer()
        backend = {
            str(header.uuid): states.FAILURE,
            str(callback.uuid): states.PENDING,
            str(legacy.uuid): states.PENDING,
        }
        before = self._snapshot()
        with (
            patch(
                "inventories.models.AsyncResult",
                side_effect=lambda key: MagicMock(state=backend[key]),
            ),
            patch("inventories.tasks.run_inventory.delay") as enqueue,
        ):
            self.assertFalse(tasks.start_inventory_run(self.scenario.pk))
        enqueue.assert_not_called()
        self.assertEqual(self._snapshot(), before)

    def test_retry_can_claim_when_only_failed_callback_is_pending(self):
        _, header = self._make_failed()
        callback = RunningTask.objects.create(
            scenario=self.scenario, uuid=uuid.uuid4(), run_id=RUN_ID
        )
        backend = {
            str(header.uuid): states.FAILURE,
            str(callback.uuid): states.PENDING,
        }
        with (
            patch(
                "inventories.models.AsyncResult",
                side_effect=lambda key: MagicMock(state=backend[key]),
            ),
            patch("inventories.tasks.run_inventory.delay") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertTrue(tasks.start_inventory_run(self.scenario.pk))
        status = self._status()
        self.assertEqual(status.status, ScenarioStatus.Status.RUNNING)
        self.assertNotEqual(status.run_id, RUN_ID)
        enqueue.assert_called_once_with(self.scenario.pk, str(status.run_id))
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())


class SettlementTestCase(LifecycleFixtures, TestCase):
    """D: settle_failed_inventory_run reconciles only when that run's tasks are READY."""

    def test_reconcile_when_all_ready_clears_markers_keeps_diag(self):
        st, rt = self._make_failed()
        rt2 = RunningTask.objects.create(
            scenario=self.scenario, uuid=uuid.uuid4(), run_id=RUN_ID
        )
        staged = self._staged_layer()
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(st.failed_algorithm_id, self.algorithm.pk)
        self.assertFalse(RunningTask.objects.filter(pk=rt.pk).exists())
        self.assertFalse(RunningTask.objects.filter(pk=rt2.pk).exists())
        self.assertFalse(Layer.all_objects.filter(pk=staged.pk).exists())

    def test_reconcile_blocked_while_any_active(self):
        st, rt = self._make_failed()
        sibling_algo = InventoryAlgorithm.objects.create(
            name="lc-algo2",
            source_module="inventories.algorithms",
            function_name="lc_fn2",
            geodataset=self.geo,
        )
        rt2 = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=sibling_algo,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        calls = iter([states.SUCCESS, states.STARTED])

        def fake(uuid_arg):
            m = MagicMock()
            m.state = next(calls)
            return m

        with patch("inventories.models.AsyncResult", side_effect=fake):
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
        self.assertTrue(RunningTask.objects.filter(pk=rt.pk).exists())
        self.assertTrue(RunningTask.objects.filter(pk=rt2.pk).exists())

    def test_reconcile_wrong_run_id_noop(self):
        st, rt = self._make_failed()
        tasks.settle_failed_inventory_run.run(self.scenario.pk, str(OTHER_RUN_ID))
        self.assertTrue(RunningTask.objects.filter(pk=rt.pk).exists())

    def test_failed_siblings_settle_without_losing_diagnostics_or_live_results(self):
        self._start_attempt()
        failed = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        sibling = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        callback = RunningTask.objects.create(
            scenario=self.scenario, uuid=uuid.uuid4(), run_id=RUN_ID
        )
        self._staged_layer()
        live = self._layer()
        foreign_stage = self._layer(
            staged=True, run_id=OTHER_RUN_ID, table_name="lc_other_stage"
        )
        backend = {
            str(failed.uuid): states.FAILURE,
            str(sibling.uuid): states.STARTED,
            str(callback.uuid): states.PENDING,
        }
        with patch(
            "inventories.models.AsyncResult",
            side_effect=lambda key: MagicMock(state=backend[key]),
        ):
            tasks.mark_inventory_failed.run(
                self.scenario.pk, str(RUN_ID), self.algorithm.pk, "first failure"
            )
            before = self._snapshot()
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
            self.assertFalse(tasks.start_inventory_run(self.scenario.pk))
            with self.assertRaises(BlockedRunningScenario):
                with transaction.atomic():
                    self.config.delete()
            self.assertEqual(self._snapshot(), before)
            backend[str(sibling.uuid)] = states.REVOKED
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
            settled = self._snapshot()
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
        self.assertEqual(self._snapshot(), settled)
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        self.assertEqual(settled["status"]["status"], ScenarioStatus.Status.FAILED)
        self.assertEqual(settled["status"]["failed_algorithm_id"], self.algorithm.pk)
        self.assertEqual(settled["status"]["failure_message"], "first failure")
        self.assertEqual(settled["status"]["run_id"], RUN_ID)
        self.assertEqual(
            set(
                Layer.all_objects.filter(scenario=self.scenario).values_list(
                    "pk", flat=True
                )
            ),
            {live.pk, foreign_stage.pk},
        )

    def test_unknown_header_state_keeps_failed_attempt_tracked(self):
        self._make_failed()
        self._staged_layer()
        before = self._snapshot()
        for state in (states.PENDING, states.RETRY, "UNKNOWN"):
            with (
                self.subTest(state=state),
                patch("inventories.models.AsyncResult", side_effect=_backend(state)),
            ):
                tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
                self.assertFalse(tasks.start_inventory_run(self.scenario.pk))
                self.assertEqual(self._snapshot(), before)


class StagingFencingTestCase(LifecycleFixtures, TestCase):
    """E: staged layers carry run_id; finalize publishes only the current generation."""

    def test_finalize_publishes_current_run_staged_prunes_out_of_plan(self):
        st = self._status()
        st.status = ScenarioStatus.Status.RUNNING
        st.run_id = RUN_ID
        st.save()
        planned = self._staged_layer(RUN_ID)
        other_gen = Layer.all_objects.create(
            name="old",
            scenario=self.scenario,
            algorithm=self.algorithm,
            feedstock=self.material,
            staged=True,
            table_name="old_tbl",
            geom_type="Polygon",
            run_id=OTHER_RUN_ID,
        )
        live_out = Layer.objects.create(
            name="live-out",
            scenario=self.scenario,
            algorithm=self.algorithm,
            feedstock=Material.objects.create(name="other-mat"),
            staged=False,
            table_name="live_tbl",
            geom_type="Polygon",
        )
        tasks.finalize_inventory.run(
            [True],
            self.scenario.pk,
            str(RUN_ID),
            [[self.algorithm.pk, self.material.pk]],
        )
        planned.refresh_from_db()
        self.assertFalse(planned.staged)
        # Other-generation staged rows are never touched by this finalizer.
        other_gen.refresh_from_db()
        self.assertTrue(other_gen.staged)
        self.assertFalse(Layer.all_objects.filter(pk=live_out.pk).exists())
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FINISHED)

    def test_run_inventory_algorithm_stages_run_id(self):
        self._start_attempt()
        with (
            patch.object(
                InventoryAlgorithm,
                "execute",
                return_value={"features": [], "geom_type": "Polygon"},
            ) as execute,
            patch("inventories.tasks.Layer.objects.create_or_replace") as stage,
        ):
            self.assertTrue(
                tasks.run_inventory_algorithm.run(
                    self.algorithm.pk,
                    scenario_id=self.scenario.pk,
                    run_id=str(RUN_ID),
                    feedstock_id=self.material.pk,
                    sample_series_id=self.series.pk,
                )
            )
        execute.assert_called_once_with(
            scenario_id=self.scenario.pk,
            feedstock_id=self.material.pk,
            sample_series_id=self.series.pk,
        )
        stage.assert_called_once()
        self.assertTrue(stage.call_args.kwargs["staged"])
        self.assertEqual(str(stage.call_args.kwargs["run_id"]), str(RUN_ID))

    def _assert_compute_cannot_stage_after(self, next_status, next_run_id):
        self._start_attempt()
        expected = {}

        def execute(**kwargs):
            ScenarioStatus.objects.filter(scenario=self.scenario).update(
                status=next_status, run_id=next_run_id
            )
            self._staged_layer(next_run_id)
            expected.update(self._snapshot())
            return {"features": [], "geom_type": "Polygon"}

        with (
            patch.object(InventoryAlgorithm, "execute", side_effect=execute),
            patch("inventories.tasks.Layer.objects.create_or_replace") as stage,
        ):
            result = tasks.run_inventory_algorithm.run(
                self.algorithm.pk,
                scenario_id=self.scenario.pk,
                run_id=str(RUN_ID),
                feedstock_id=self.material.pk,
            )
        self.assertIsNone(result)
        stage.assert_not_called()
        self.assertEqual(self._snapshot(), expected)

    def test_algorithm_cannot_stage_over_new_run_after_computation(self):
        self._assert_compute_cannot_stage_after(
            ScenarioStatus.Status.RUNNING, OTHER_RUN_ID
        )

    def test_algorithm_cannot_stage_after_sibling_failure(self):
        self._assert_compute_cannot_stage_after(ScenarioStatus.Status.FAILED, RUN_ID)

    def test_algorithm_cannot_stage_after_input_invalidation(self):
        self._assert_compute_cannot_stage_after(ScenarioStatus.Status.CHANGED, None)

    def test_legacy_missing_identity_is_rejected_before_algorithm_lookup(self):
        self._start_attempt(run_id=None)
        before = self._snapshot()
        with patch(
            "inventories.tasks.InventoryAlgorithm.objects.get",
            side_effect=AssertionError("A legacy task must not execute"),
        ) as lookup:
            for invalid in (None, "None", "not-a-uuid"):
                with self.subTest(run_id=invalid):
                    self.assertIsNone(
                        tasks.run_inventory_algorithm.run(
                            self.algorithm.pk,
                            scenario_id=self.scenario.pk,
                            run_id=invalid,
                            feedstock_id=self.material.pk,
                        )
                    )
        lookup.assert_not_called()
        self.assertEqual(self._snapshot(), before)

    def test_finalize_requires_running_current_generation(self):
        st = self._status()
        st.status = ScenarioStatus.Status.FAILED
        st.run_id = RUN_ID
        st.save()
        before_tasks = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        staged = self._staged_layer(RUN_ID)
        # FAILED + matching run -> NoOp; results never validated.
        tasks.finalize_inventory.run([True], self.scenario.pk, str(RUN_ID))
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FAILED)
        staged.refresh_from_db()
        self.assertTrue(staged.staged)
        self.assertTrue(RunningTask.objects.filter(pk=before_tasks.pk).exists())

    def test_finalize_stale_run_noop_before_result_validation(self):
        st = self._status()
        st.status = ScenarioStatus.Status.RUNNING
        st.run_id = RUN_ID
        st.save()
        staged = self._staged_layer(RUN_ID)
        # Stale generation must not even raise for bad results.
        tasks.finalize_inventory.run([False], self.scenario.pk, str(OTHER_RUN_ID))
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.RUNNING)
        staged.refresh_from_db()
        self.assertTrue(staged.staged)

    def test_finalize_duplicate_finished_noop(self):
        st = self._status()
        st.status = ScenarioStatus.Status.FINISHED
        st.run_id = RUN_ID
        st.save()
        staged = self._staged_layer(RUN_ID)
        tasks.finalize_inventory.run([True], self.scenario.pk, str(RUN_ID))
        st.refresh_from_db()
        self.assertEqual(st.status, ScenarioStatus.Status.FINISHED)
        staged.refresh_from_db()
        self.assertTrue(staged.staged)

    def test_is_defined_by_run_id(self):
        layer = self._staged_layer(RUN_ID)
        kwargs = {
            "table_name": "lc_tbl",
            "geom_type": "Polygon",
            "scenario": self.scenario,
            "algorithm": self.algorithm,
            "fields": {},
        }
        self.assertTrue(layer.is_defined_by(run_id=RUN_ID, **kwargs))
        self.assertTrue(layer.is_defined_by(run_id=str(RUN_ID), **kwargs))
        self.assertFalse(layer.is_defined_by(run_id=OTHER_RUN_ID, **kwargs))
        self.assertFalse(layer.is_defined_by(run_id=None, **kwargs))


class FailurePairingTestCase(LifecycleFixtures, TestCase):
    def _run_failed(self, algo=None, msg=""):
        st = self._status()
        st.status = ScenarioStatus.Status.RUNNING
        st.run_id = RUN_ID
        st.save()
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), algo and algo.pk, msg
        )
        st.refresh_from_db()
        return st

    def test_first_specific_algorithm_and_message_form_the_pair(self):
        self._run_failed(self.algorithm, "algo A boom")
        other = InventoryAlgorithm.objects.create(
            name="lc-b",
            source_module="inventories.algorithms",
            function_name="lc_b",
            geodataset=self.geo,
        )
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), other.pk, "algo B boom"
        )
        st = self._status()
        self.assertEqual(st.failed_algorithm_id, self.algorithm.pk)
        self.assertEqual(st.failure_message, "algo A boom")
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), None, "generic repeat"
        )
        st.refresh_from_db()
        self.assertEqual(st.failed_algorithm_id, self.algorithm.pk)
        self.assertEqual(st.failure_message, "algo A boom")

    def test_generic_failure_upgraded_by_first_specific_pair(self):
        self._run_failed(None, "setup failed")
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), self.algorithm.pk, "algo A boom"
        )
        st = self._status()
        self.assertEqual(st.failed_algorithm_id, self.algorithm.pk)
        self.assertEqual(st.failure_message, "algo A boom")

    def test_specific_failure_without_message_does_not_keep_generic_diagnostic(self):
        self._run_failed(None, "unrelated generic diagnostic")
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), self.algorithm.pk, ""
        )
        status = self._status()
        self.assertEqual(status.failed_algorithm_id, self.algorithm.pk)
        self.assertEqual(status.failure_message, "")


class StaleGenerationNoOpsTestCase(LifecycleFixtures, TestCase):
    """Every entry point must NoOp for a stale run while a NEW run is RUNNING."""

    def setUp(self):
        st = self._status()
        st.status = ScenarioStatus.Status.RUNNING
        st.run_id = RUN_ID
        st.save()

    def test_stale_launch_algorithm_failure_finalize_cleanup_all_noop(self):
        before = self._snapshot()
        self.assertIsNone(tasks.run_inventory.run(self.scenario.pk, str(OTHER_RUN_ID)))
        self.assertIsNone(
            tasks.run_inventory_algorithm.run(
                self.algorithm.pk,
                scenario_id=self.scenario.pk,
                run_id=str(OTHER_RUN_ID),
                feedstock_id=self.material.pk,
            )
        )
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(OTHER_RUN_ID), self.algorithm.pk, "stale"
        )
        tasks.finalize_inventory.run([True], self.scenario.pk, str(OTHER_RUN_ID))
        tasks.settle_failed_inventory_run.run(self.scenario.pk, str(OTHER_RUN_ID))
        self.assertEqual(self._snapshot(), before)

    def test_pending_claim_running_no_rows_rejects_second_start(self):
        with patch("inventories.tasks.run_inventory.delay") as delay:
            ok = tasks.start_inventory_run(self.scenario.pk)
        self.assertFalse(ok)
        delay.assert_not_called()

    def test_run_inventory_noop_when_rows_already_registered(self):
        RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        with patch("inventories.tasks.chord") as chord_m:
            self.assertIsNone(tasks.run_inventory.run(self.scenario.pk, str(RUN_ID)))
        chord_m.assert_not_called()

    def test_deleted_scenario_is_ignored_before_algorithm_lookup(self):
        ScenarioStatus.objects.filter(scenario=self.scenario).update(
            status=ScenarioStatus.Status.CHANGED, run_id=None
        )
        scenario_id = self.scenario.pk
        self.scenario.delete()
        with patch(
            "inventories.tasks.InventoryAlgorithm.objects.get",
            side_effect=AssertionError("A deleted scenario must not execute"),
        ) as lookup:
            self.assertIsNone(
                tasks.run_inventory_algorithm.run(
                    self.algorithm.pk,
                    scenario_id=scenario_id,
                    run_id=str(RUN_ID),
                    feedstock_id=self.material.pk,
                )
            )
        lookup.assert_not_called()


class IdentityHelperTestCase(TestCase):
    def test_is_current_inventory_run_rejects_none_and_malformed(self):
        st = MagicMock()
        st.run_id = None
        self.assertFalse(is_current_inventory_run(st, None))
        self.assertFalse(is_current_inventory_run(st, str(uuid.uuid4())))
        st.run_id = uuid.uuid4()
        self.assertFalse(is_current_inventory_run(st, None))
        self.assertFalse(is_current_inventory_run(st, "None"))
        self.assertFalse(is_current_inventory_run(st, "not-a-uuid"))
        self.assertTrue(is_current_inventory_run(st, str(st.run_id)))
        self.assertTrue(is_current_inventory_run(st, st.run_id))


class CompletionHookTestCase(LifecycleFixtures, TestCase):
    def test_after_return_calls_super_and_enqueues_only_terminal_states(self):
        hook = tasks.InventoryAlgorithmTask()
        kwargs = {"scenario_id": self.scenario.pk, "run_id": str(RUN_ID)}
        for status in (states.SUCCESS, states.FAILURE, states.RETRY):
            with (
                self.subTest(status=status),
                patch.object(
                    tasks.InventoryAlgorithmTask.__base__, "after_return", autospec=True
                ) as parent,
                patch("inventories.tasks.settle_failed_inventory_run.delay") as enqueue,
            ):
                hook.after_return(status, None, "task-id", (), kwargs, None)
                parent.assert_called_once_with(
                    hook, status, None, "task-id", (), kwargs, None
                )
                if status in states.READY_STATES:
                    enqueue.assert_called_once_with(self.scenario.pk, str(RUN_ID))
                else:
                    enqueue.assert_not_called()

    def test_enqueue_failure_does_not_mask_primary_algorithm_failure(self):
        self._start_attempt()
        marker = RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        with (
            self.assertLogs("inventories.tasks", level="WARNING") as logs,
            patch.object(
                InventoryAlgorithm,
                "execute",
                side_effect=RuntimeError("primary failure"),
            ),
            patch(
                "inventories.tasks.settle_failed_inventory_run.delay",
                side_effect=RuntimeError("broker unavailable"),
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            with self.assertRaisesMessage(RuntimeError, "primary failure"):
                tasks.run_inventory_algorithm.run(
                    self.algorithm.pk,
                    scenario_id=self.scenario.pk,
                    run_id=str(RUN_ID),
                    feedstock_id=self.material.pk,
                )
        self.assertIn("Failed to enqueue settlement", "\n".join(logs.output))
        self.assertTrue(RunningTask.objects.filter(pk=marker.pk).exists())
        self.assertEqual(self._status().failure_message, "primary failure")

    def test_no_header_setup_failure_settles_without_deleting_live_results(self):
        self._start_attempt()
        self._staged_layer()
        live = self._layer()
        with (
            patch.object(
                Scenario,
                "inventory_execution_plan",
                side_effect=RuntimeError("setup failed"),
            ),
            patch(
                "inventories.tasks.settle_failed_inventory_run.delay",
                side_effect=tasks.settle_failed_inventory_run.run,
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            with self.assertRaisesMessage(RuntimeError, "setup failed"):
                tasks.run_inventory.run(self.scenario.pk, str(RUN_ID))
        status = self._status()
        self.assertEqual(status.status, ScenarioStatus.Status.FAILED)
        self.assertEqual(status.failure_message, "setup failed")
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())
        self.assertEqual(
            list(
                Layer.all_objects.filter(scenario=self.scenario).values_list(
                    "pk", flat=True
                )
            ),
            [live.pk],
        )

    def test_failed_finalizer_rolls_back_and_errback_keeps_live_outputs(self):
        self._start_attempt()
        self._staged_layer()
        live = self._layer()
        RunningTask.objects.create(
            scenario=self.scenario,
            algorithm=self.algorithm,
            uuid=uuid.uuid4(),
            run_id=RUN_ID,
        )
        before = self._snapshot()
        with patch.object(Layer, "publish", side_effect=RuntimeError("publish failed")):
            with self.assertRaisesMessage(RuntimeError, "publish failed"):
                tasks.finalize_inventory.run([True], self.scenario.pk, str(RUN_ID))
        self.assertEqual(self._snapshot(), before)
        tasks.mark_inventory_failed.run(
            self.scenario.pk, str(RUN_ID), failure_message="publish failed"
        )
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            tasks.settle_failed_inventory_run.run(self.scenario.pk, str(RUN_ID))
        self.assertEqual(self._status().status, ScenarioStatus.Status.FAILED)
        self.assertEqual(self._status().failure_message, "publish failed")
        self.assertTrue(Layer.objects.filter(pk=live.pk).exists())
        self.assertFalse(RunningTask.objects.filter(scenario=self.scenario).exists())


class AuditRollbackTestCase(LifecycleFixtures, TestCase):
    """An audit-persist failure must roll back the entire governed removal."""

    def test_remove_audit_failure_rolls_back_config_and_state(self):
        st, rt = self._make_failed()
        staged, features = Layer.objects.create_or_replace(
            staged=True,
            run_id=RUN_ID,
            scenario=self.scenario,
            algorithm=self.algorithm,
            feedstock=self.material,
            name="rollback-stage",
            results={
                "features": [
                    {
                        "geom": Polygon(
                            ((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)),
                            srid=4326,
                        ),
                        "amount": 1.0,
                    }
                ]
            },
        )
        owner_perms = Permission.objects.get(codename="change_scenario")
        self.owner.user_permissions.add(owner_perms)
        client = Client()
        client.force_login(self.owner)
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.material.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        before = self._snapshot()
        before_features = list(features.objects.order_by("pk").values())

        def audit_failure(**kwargs):
            self.assertFalse(
                ScenarioInventoryConfiguration.objects.filter(
                    pk=self.config.pk
                ).exists()
            )
            self.assertEqual(self._status().status, ScenarioStatus.Status.CHANGED)
            self.assertFalse(RunningTask.objects.filter(pk=rt.pk).exists())
            self.assertFalse(Layer.all_objects.filter(pk=staged.pk).exists())
            raise RuntimeError("audit fail after deletion")

        with (
            self.assertLogs("django.request", level="ERROR") as logs,
            patch(
                "inventories.models.AsyncResult",
                side_effect=_backend(states.SUCCESS),
            ),
            patch(
                "utils.object_management.services.ReviewAction.objects.create",
                side_effect=audit_failure,
            ),
        ):
            with self.assertRaisesMessage(RuntimeError, "audit fail after deletion"):
                client.post(url)
        self.assertIn("Internal Server Error", "\n".join(logs.output))
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(
            list(features.objects.order_by("pk").values()), before_features
        )


class CascadeDeleteTestCase(LifecycleFixtures, TestCase):
    def test_quiescent_scenario_delete_resurrects_no_status(self):
        st, rt = self._make_failed()
        scenario_id = self.scenario.pk
        with patch(
            "inventories.models.AsyncResult", side_effect=_backend(states.SUCCESS)
        ):
            self.scenario.delete()
        self.assertFalse(Scenario.objects.filter(pk=scenario_id).exists())
        self.assertFalse(
            ScenarioStatus.objects.filter(scenario_id=scenario_id).exists()
        )


class LockedEvaluationHelperTestCase(LifecycleFixtures, TestCase):
    def test_lock_yields_scenario_status_tasks(self):
        self._make_failed()
        with locked_scenario_evaluation(self.scenario.pk) as result:
            self.assertIsNotNone(result)
            sc, st, task_list = result
            self.assertEqual(sc.pk, self.scenario.pk)
            self.assertEqual(st.status, ScenarioStatus.Status.FAILED)
            self.assertEqual(len(task_list), 1)

    def test_lock_none_for_missing_scenario(self):
        with locked_scenario_evaluation(999999) as result:
            self.assertIsNone(result)
