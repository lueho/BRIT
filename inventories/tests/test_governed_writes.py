"""Boundary regressions for the migrated inventories domain writers.

Scenario configuration rows are owned children of the Scenario root: the
legacy ``policy["can_edit"]`` dict gates are replaced by the central
``decide`` and the remove/add writes run inside ``content_mutation`` on
the scenario, so denied actors write nothing and allowed writes bump the
scenario revision and record the audit event.
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
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

    def test_get_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.scenario)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )
        self.assertEqual(_revision(self.scenario), revision)

    def test_get_authorized_removes_config_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.scenario)
        response = self.client.get(self.url())
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
