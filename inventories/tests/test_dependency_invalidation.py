"""Dependency edits must not silently invalidate or roll over a running
evaluation. A referencing scenario locked by pending/active work rejects the
dependency save atomically; a quiescent scenario is invalidated canonically."""

import threading
import uuid
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from bibliography.models import Source
from inventories.exceptions import BlockedRunningScenario
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
    locked_scenario_evaluation,
)
from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, SampleSeries

from .test_evaluation_lifecycle import RUN_ID, LifecycleFixtures, _backend, _events_for


def _dependency_rows():
    return {
        "algorithms": list(InventoryAlgorithm.objects.order_by("pk").values()),
        "values": list(
            InventoryAlgorithmParameterValue.objects.order_by("pk").values()
        ),
        "feedstock_m2m": list(
            InventoryAlgorithm.feedstocks.through.objects.order_by("pk").values()
        ),
    }


def _scenario_snapshot(scenario):
    return {
        "scenario": Scenario.objects.filter(pk=scenario.pk).values().get(),
        "status": ScenarioStatus.objects.filter(scenario=scenario).values().get(),
        "configs": list(
            ScenarioInventoryConfiguration.objects.filter(scenario=scenario)
            .order_by("pk")
            .values()
        ),
        "tasks": list(
            RunningTask.objects.filter(scenario=scenario).order_by("pk").values()
        ),
        "layers": list(
            Layer.all_objects.filter(scenario=scenario).order_by("pk").values()
        ),
        "layer_fields": list(
            Layer.layer_fields.through.objects.filter(layer__scenario=scenario)
            .order_by("pk")
            .values()
        ),
        "audits": list(_events_for(scenario).order_by("pk").values()),
        "admin_logs": list(LogEntry.objects.order_by("pk").values()),
    }


class DependencyGuardTestCase(LifecycleFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="dep-param", short_name="dep"
        )
        cls.value = InventoryAlgorithmParameterValue.objects.create(
            name="dep-value", parameter=cls.parameter, value=2.0
        )
        cls.config.inventory_parameter = cls.parameter
        cls.config.inventory_value = cls.value
        cls.config.save()

    def _save_algo(self, partial=False):
        self.algorithm.refresh_from_db()
        self.algorithm.description = "edited-algo"
        if partial:
            self.algorithm.save(update_fields=["description"])
        else:
            self.algorithm.save()

    def _save_value(self, partial=False):
        self.value.refresh_from_db()
        self.value.value = 7.0
        if partial:
            self.value.save(update_fields=["value"])
        else:
            self.value.save()

    def _snapshot_deps(self):
        return _dependency_rows()

    def test_pending_running_rejects_both_kinds_full_and_partial(self):
        self._start_attempt()
        for kind in ("algo", "value"):
            for partial in (False, True):
                with self.subTest(kind=kind, partial=partial):
                    before = _scenario_snapshot(self.scenario)
                    before_deps = self._snapshot_deps()
                    with self.assertRaises(BlockedRunningScenario):
                        (self._save_algo if kind == "algo" else self._save_value)(
                            partial=partial
                        )
                    self.assertEqual(_scenario_snapshot(self.scenario), before)
                    self.assertEqual(self._snapshot_deps(), before_deps)

    def test_running_with_active_markers_rejects_both(self):
        self._start_attempt()
        self._staged_layer()
        self._layer(run_id=RUN_ID, staged=False, table_name="lc_live")
        for kind in ("algo", "value"):
            for state in ("PENDING", "STARTED", "RETRY"):
                rt = RunningTask.objects.create(
                    scenario=self.scenario,
                    algorithm=self.algorithm,
                    uuid=uuid.uuid4(),
                    run_id=RUN_ID,
                )
                before = _scenario_snapshot(self.scenario)
                before_deps = self._snapshot_deps()
                with self.subTest(kind=kind, state=state):
                    with patch(
                        "inventories.models.AsyncResult",
                        side_effect=_backend(state),
                    ):
                        with self.assertRaises(BlockedRunningScenario):
                            (self._save_algo if kind == "algo" else self._save_value)()
                    self.assertEqual(_scenario_snapshot(self.scenario), before)
                    self.assertEqual(self._snapshot_deps(), before_deps)
                rt.delete()

    def test_failed_with_active_work_rejects_both(self):
        self._make_failed()
        self._staged_layer()
        for kind in ("algo", "value"):
            with self.subTest(kind=kind):
                before = _scenario_snapshot(self.scenario)
                before_deps = self._snapshot_deps()
                with patch(
                    "inventories.models.AsyncResult",
                    side_effect=_backend("STARTED"),
                ):
                    with self.assertRaises(BlockedRunningScenario):
                        (self._save_algo if kind == "algo" else self._save_value)()
                self.assertEqual(_scenario_snapshot(self.scenario), before)
                self.assertEqual(self._snapshot_deps(), before_deps)

    def test_shared_dependency_atomic_rejection(self):
        scenario2 = Scenario.objects.create(
            name="lc-sc2",
            region=self.region,
            catchment=self.catchment,
            owner=self.owner,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=scenario2,
            feedstock=self.material,
            geodataset=self.geo,
            inventory_algorithm=self.algorithm,
            inventory_parameter=self.parameter,
            inventory_value=self.value,
        )
        ScenarioStatus.objects.get_or_create(scenario=scenario2)
        status1 = self._status()
        status1.status = ScenarioStatus.Status.FAILED
        status1.run_id = RUN_ID
        status1.failed_algorithm = self.algorithm
        status1.failure_message = "Earlier settled failure"
        status1.save()
        self._staged_layer()
        status2 = ScenarioStatus.objects.get(scenario=scenario2)
        status2.status = ScenarioStatus.Status.RUNNING
        status2.run_id = RUN_ID
        status2.save()
        for kind in ("algo", "value"):
            with self.subTest(kind=kind):
                before1 = _scenario_snapshot(self.scenario)
                before2 = _scenario_snapshot(scenario2)
                before_deps = self._snapshot_deps()
                with self.assertRaises(BlockedRunningScenario):
                    (self._save_algo if kind == "algo" else self._save_value)()
                self.assertEqual(_scenario_snapshot(self.scenario), before1)
                self.assertEqual(_scenario_snapshot(scenario2), before2)
                self.assertEqual(self._snapshot_deps(), before_deps)

    def test_quiescent_allows_changed_and_cleanup(self):
        scenario2 = Scenario.objects.create(
            name="lc-sc3",
            region=self.region,
            catchment=self.catchment,
            owner=self.owner,
        )
        ScenarioStatus.objects.get_or_create(scenario=scenario2)
        status2 = ScenarioStatus.objects.get(scenario=scenario2)
        status2.status = ScenarioStatus.Status.FINISHED
        status2.save()
        unrelated_before = _scenario_snapshot(scenario2)
        for state in ("RUNNING", "FAILED"):
            for kind in ("algo", "value"):
                with self.subTest(state=state, kind=kind), transaction.atomic():
                    if state == "RUNNING":
                        self._start_attempt()
                    else:
                        self._make_failed()
                    rt = RunningTask.objects.create(
                        scenario=self.scenario,
                        algorithm=self.algorithm,
                        uuid=uuid.uuid4(),
                        run_id=RUN_ID,
                    )
                    staged = self._layer(
                        run_id=RUN_ID,
                        staged=True,
                        table_name=f"lc_st_{state.lower()}_{kind}_{rt.pk}",
                    )
                    live = self._layer(
                        run_id=RUN_ID,
                        staged=False,
                        table_name=f"lc_lv_{state.lower()}_{kind}_{rt.pk}",
                    )
                    before_deps = self._snapshot_deps()
                    with patch(
                        "inventories.models.AsyncResult",
                        side_effect=_backend("SUCCESS"),
                    ):
                        (self._save_algo if kind == "algo" else self._save_value)()
                    st = self._status()
                    self.assertEqual(st.status, ScenarioStatus.Status.CHANGED)
                    self.assertIsNone(st.run_id)
                    self.assertIsNone(st.failed_algorithm_id)
                    self.assertEqual(st.failure_message, "")
                    self.assertFalse(
                        RunningTask.objects.filter(scenario=self.scenario).exists()
                    )
                    self.assertFalse(
                        staged.__class__.all_objects.filter(pk=staged.pk).exists()
                    )
                    self.assertTrue(
                        live.__class__.all_objects.filter(pk=live.pk).exists()
                    )
                    after_deps = self._snapshot_deps()
                    if kind == "algo":
                        self.assertEqual(
                            InventoryAlgorithm.objects.get(
                                pk=self.algorithm.pk
                            ).description,
                            "edited-algo",
                        )
                        self.assertEqual(after_deps["values"], before_deps["values"])
                    else:
                        self.assertEqual(
                            InventoryAlgorithmParameterValue.objects.get(
                                pk=self.value.pk
                            ).value,
                            7.0,
                        )
                        self.assertEqual(
                            after_deps["algorithms"], before_deps["algorithms"]
                        )
                    self.assertEqual(_scenario_snapshot(scenario2), unrelated_before)
                    transaction.set_rollback(True)

    def test_unreferenced_dependency_allows_both(self):
        other_algo = InventoryAlgorithm.objects.create(
            name="other-algo",
            source_module="inventories.algorithms",
            function_name="other_fn",
            geodataset=self.geo,
        )
        other_value = InventoryAlgorithmParameterValue.objects.create(
            name="other-value", parameter=self.parameter, value=9.0
        )
        self._start_attempt()
        before = _scenario_snapshot(self.scenario)
        other_algo.description = "changed"
        other_algo.save()
        other_value.value = 42.0
        other_value.save()
        self.assertEqual(
            InventoryAlgorithm.objects.get(pk=other_algo.pk).description, "changed"
        )
        self.assertEqual(
            InventoryAlgorithmParameterValue.objects.get(pk=other_value.pk).value,
            42.0,
        )
        self.assertEqual(_scenario_snapshot(self.scenario), before)

    def test_default_fanout_atomic_rollback(self):
        v1 = InventoryAlgorithmParameterValue.objects.create(
            name="v1", parameter=self.parameter, value=1.0, default=True
        )
        self.config.inventory_value = v1
        self.config.save()
        v2 = InventoryAlgorithmParameterValue.objects.create(
            name="v2", parameter=self.parameter, value=3.0, default=False
        )
        self._start_attempt()
        before_deps = self._snapshot_deps()
        before = _scenario_snapshot(self.scenario)
        with self.assertRaises(BlockedRunningScenario):
            v2.default = True
            v2.save()
        self.assertEqual(self._snapshot_deps(), before_deps)
        self.assertEqual(_scenario_snapshot(self.scenario), before)

    def test_admin_post_returns_409_and_preserves(self):
        admin = User.objects.create_superuser("dep-admin", "a@x", "pw")
        source = Source.objects.create(
            title="dep-src", owner=admin, publication_status="published"
        )
        self.algorithm.source = source
        self.algorithm.save()
        self._start_attempt()
        self.client.force_login(admin)
        for label, url, payload in (
            (
                "algorithm",
                reverse(
                    "admin:inventories_inventoryalgorithm_change",
                    args=[self.algorithm.pk],
                ),
                {
                    "name": "edited-admin",
                    "source_module": self.algorithm.source_module,
                    "function_name": self.algorithm.function_name,
                    "geodataset": self.geo.pk,
                    "source": source.pk,
                    "feedstocks": [self.material.pk],
                },
            ),
            (
                "value",
                reverse(
                    "admin:inventories_inventoryalgorithmparametervalue_change",
                    args=[self.value.pk],
                ),
                {
                    "name": "edited-value",
                    "type": self.value.type,
                    "parameter": self.parameter.pk,
                    "value": 99.0,
                    "standard_deviation": 0.0,
                    "default": "on",
                },
            ),
        ):
            with self.subTest(kind=label):
                before = _scenario_snapshot(self.scenario)
                before_deps = self._snapshot_deps()
                resp = self.client.post(url, payload)
                self.assertEqual(resp.status_code, 409)
                self.assertIn("still in progress", resp.content.decode())
                self.assertEqual(_scenario_snapshot(self.scenario), before)
                self.assertEqual(self._snapshot_deps(), before_deps)


class DependencyLockRaceTestCase(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user("race-owner")
        self.region = Region.objects.create(name="race-region", country="DE")
        self.catchment = Catchment.objects.create(
            name="race-catch", region=self.region, parent_region=self.region
        )
        self.material = Material.objects.create(name="race-mat")
        self.series = SampleSeries.objects.create(
            name="race-ss", material=self.material
        )
        self.geo = GeoDataset.objects.create(name="race-geo", region=self.region)
        self.algorithm = InventoryAlgorithm.objects.create(
            name="race-algo",
            source_module="inventories.algorithms",
            function_name="race_fn",
            geodataset=self.geo,
        )
        self.scenario = Scenario.objects.create(
            name="race-sc",
            region=self.region,
            catchment=self.catchment,
            owner=self.owner,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.material,
            geodataset=self.geo,
            inventory_algorithm=self.algorithm,
        )
        ScenarioStatus.objects.get_or_create(scenario=self.scenario)

    @skipUnlessDBFeature("has_select_for_update")
    def test_worker_save_blocked_while_lock_held(self):
        ready = threading.Event()
        done = threading.Event()
        result = {}

        def worker():
            try:
                algo = InventoryAlgorithm.objects.using("default").get(
                    pk=self.algorithm.pk
                )
                algo.description = "race-write"
                ready.set()
                algo.save()
                result["saved"] = True
            except Exception as exc:
                result["error"] = exc
            finally:
                done.set()
                connections["default"].close()

        t = threading.Thread(target=worker, daemon=True)
        try:
            with locked_scenario_evaluation(self.scenario.pk) as locked:
                _, status, _ = locked
                status.status = ScenarioStatus.Status.RUNNING
                status.run_id = RUN_ID
                status.save()
                t.start()
                self.assertTrue(ready.wait(timeout=10))
                self.assertFalse(done.wait(timeout=0.25))
        finally:
            if t.ident is not None:
                t.join(timeout=10)
        self.assertFalse(t.is_alive())
        self.assertIsInstance(result.get("error"), BlockedRunningScenario)
        self.assertNotIn("saved", result)
        self.assertEqual(
            InventoryAlgorithm.objects.get(pk=self.algorithm.pk).description,
            self.algorithm.description,
        )
        st = ScenarioStatus.objects.get(scenario=self.scenario)
        self.assertEqual(st.status, ScenarioStatus.Status.RUNNING)
        self.assertEqual(st.run_id, RUN_ID)
