"""Boundary regressions for the migrated inventories domain writers.

Scenario configuration rows are owned children of the Scenario root: the
legacy ``policy["can_edit"]`` dict gates are replaced by the central
``decide`` and the remove/add writes run inside ``content_mutation`` on
the scenario, so denied actors write nothing and allowed writes bump the
scenario revision and record the audit event.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse

from distributions.models import TemporalDistribution
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material
from utils.object_management.models import ReviewAction
from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import (
    InventoryAlgorithm,
    Scenario,
    ScenarioInventoryConfiguration,
)


def _events_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
    )


def _revision(obj):
    return type(obj)._base_manager.get(pk=obj.pk).content_revision


class ScenarioConfigFixtures:
    """Shared fixture builders for the scenario-configuration boundaries."""

    @classmethod
    def make_config(cls, owner):
        cls.region = Region.objects.create(
            name="GW Region", publication_status="published"
        )
        cls.catchment = Catchment.objects.create(
            name="GW Catchment",
            region=cls.region,
            parent_region=cls.region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="GW Scenario", owner=owner, region=cls.region, catchment=cls.catchment
        )
        cls.feedstock = Material.objects.create(name="GW Feedstock")
        cls.geodataset = GeoDataset.objects.create(
            name="GW GeoDataset",
            owner=owner,
            region=cls.region,
            publication_status="published",
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="GW Algorithm", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(cls.feedstock)

    @classmethod
    def config_row(cls):
        return ScenarioInventoryConfiguration.objects.create(
            scenario=cls.scenario,
            feedstock=cls.feedstock,
            geodataset=cls.geodataset,
            inventory_algorithm=cls.algorithm,
        )


class ScenarioAddInventoryAlgorithmBoundaryTestCase(
    ViewWithPermissionsTestCase, ScenarioConfigFixtures
):
    member_permissions = "change_scenario"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.make_config(cls.owner)
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )

    def url(self):
        return reverse("scenario-add-configuration", kwargs={"pk": self.scenario.pk})

    def post_data(self):
        return {
            "feedstock": self.feedstock.pk,
            "inventory_algorithm": self.algorithm.pk,
        }

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.scenario)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )
        self.assertEqual(_revision(self.scenario), revision)

    def test_post_authorized_writes_config_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.scenario)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                feedstock=self.feedstock,
                inventory_algorithm=self.algorithm,
            ).exists()
        )
        self.assertEqual(_revision(self.scenario), revision + 1)
        self.assertTrue(
            _events_for(self.scenario)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )


class ScenarioAlgorithmConfigurationUpdateBoundaryTestCase(
    ViewWithPermissionsTestCase, ScenarioConfigFixtures
):
    """The remove+add replacement runs atomically inside the scenario's
    content_mutation boundary."""

    member_permissions = "change_scenario"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.make_config(cls.owner)
        cls.config = cls.config_row()
        cls.new_algorithm = InventoryAlgorithm.objects.create(
            name="GW New Algorithm", geodataset=cls.geodataset
        )
        cls.new_algorithm.feedstocks.add(cls.feedstock)
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )

    def url(self):
        return reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def post_data(self):
        return {
            "feedstock": self.feedstock.pk,
            "inventory_algorithm": self.new_algorithm.pk,
        }

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.scenario)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(_revision(self.scenario), revision)

    def test_post_authorized_replaces_config_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.scenario)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                inventory_algorithm=self.new_algorithm,
            ).exists()
        )
        self.assertEqual(_revision(self.scenario), revision + 1)
        self.assertTrue(
            _events_for(self.scenario)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )


class ScenarioRemoveInventoryAlgorithmBoundaryTestCase(
    ViewWithPermissionsTestCase, ScenarioConfigFixtures
):
    member_permissions = "change_scenario"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.make_config(cls.owner)
        cls.config = cls.config_row()
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )

    def url(self):
        return reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def _snapshot(self):
        """Every field/row the boundary must leave untouched."""
        return {
            "scenario": type(self.scenario)
            ._base_manager.filter(pk=self.scenario.pk)
            .values()
            .get(),
            "configs": list(
                ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario)
                .order_by("pk")
                .values()
            ),
            "events": list(_events_for(self.scenario).order_by("pk").values()),
        }

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        before = self._snapshot()
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client.post(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(any("Forbidden" in line for line in logs.output), logs.output)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(self._snapshot(), before)

    def test_post_authorized_removes_config_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.scenario)
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(_revision(self.scenario), revision + 1)
        self.assertTrue(
            _events_for(self.scenario)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )

    def test_get_authorized_returns_405_without_mutation(self):
        self.client.force_login(self.owner)
        before = self._snapshot()
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client.get(self.url())
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            any(
                "Method Not Allowed" in line and self.url() in line
                for line in logs.output
            ),
            logs.output,
        )
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(self._snapshot(), before)

    def test_post_denied_for_outsider(self):
        self.client.force_login(self.outsider)
        before = self._snapshot()
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client.post(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(any("Forbidden" in line for line in logs.output), logs.output)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(self._snapshot(), before)

    def test_post_denied_for_owner_without_change_capability(self):
        self.owner.user_permissions.clear()
        self.owner.groups.clear()
        owner = get_user_model().objects.get(pk=self.owner.pk)
        self.assertFalse(owner.has_perm("inventories.change_scenario"))
        self.client.force_login(owner)
        before = self._snapshot()
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client.post(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(any("Forbidden" in line for line in logs.output), logs.output)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(self._snapshot(), before)

    # testrunner strips CsrfViewMiddleware; inject it here so the enforcement
    # path is the production-real one, not a skipped check.
    @override_settings(
        MIDDLEWARE=[
            *settings.MIDDLEWARE,
            "django.middleware.csrf.CsrfViewMiddleware",
        ]
    )
    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        detail = reverse("scenario-detail", kwargs={"pk": self.scenario.pk})
        bootstrap = client.get(detail)
        self.assertEqual(bootstrap.status_code, 200)
        self.assertIn(settings.CSRF_COOKIE_NAME, client.cookies)
        before = self._snapshot()
        with self.assertLogs("django.security.csrf", "WARNING") as logs:
            response = client.post(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(any("Forbidden" in line for line in logs.output), logs.output)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(self._snapshot(), before)

    # testrunner strips CsrfViewMiddleware; inject it here so the valid-token
    # path exercises the production middleware, not a skipped check.
    @override_settings(
        MIDDLEWARE=[
            *settings.MIDDLEWARE,
            "django.middleware.csrf.CsrfViewMiddleware",
        ]
    )
    def test_post_with_valid_csrf_removes_config_with_revision_and_audit(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        detail = reverse("scenario-detail", kwargs={"pk": self.scenario.pk})
        bootstrap = client.get(detail)
        self.assertEqual(bootstrap.status_code, 200)
        self.assertIn(settings.CSRF_COOKIE_NAME, client.cookies)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        revision = _revision(self.scenario)
        response = client.post(self.url(), {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(_revision(self.scenario), revision + 1)
        new_events = list(
            _events_for(self.scenario).filter(action=ReviewAction.ACTION_EDITED)
        )
        self.assertEqual(len(new_events), 1)
        self.assertEqual(new_events[0].user_id, self.owner.pk)
        self.assertEqual(new_events[0].content_revision, revision + 1)

    def test_scenario_detail_remove_control_is_post_form(self):
        self.client.force_login(self.owner)
        detail = reverse("scenario-detail", kwargs={"pk": self.scenario.pk})
        response = self.client.get(detail)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn(f'href="{self.url()}"', html)
        match = re.search(
            rf'<form[^>]*action="{re.escape(self.url())}"[^>]*>(.*?)</form>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "remove form missing")
        tag = match.group(0)
        self.assertIn('method="post"', match.group(0)[: match.group(0).index(">")])
        self.assertIn("csrfmiddlewaretoken", tag)
        self.assertIn('type="submit"', tag)


class SeasonalDistributionCreateBoundaryTestCase(ViewWithPermissionsTestCase):
    """TemporalDistribution is a registered reviewable model: the create
    route now runs the governed bound-create — the central ``create``
    decision, boundary-assigned owner/status, and the ``created`` audit
    event."""

    member_permissions = "add_temporaldistribution"

    def url(self):
        return reverse(
            "seasonal-distribution-create",
            kwargs={"material_pk": 1, "component_pk": 1},
        )

    def test_post_denied_without_create_capability(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            TemporalDistribution.objects.filter(owner=self.outsider).exists()
        )

    def test_post_authorized_creates_distribution_with_audit(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 302)
        distribution = TemporalDistribution.objects.get(owner=self.member)
        self.assertEqual(distribution.publication_status, "private")
        self.assertTrue(
            _events_for(distribution)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
