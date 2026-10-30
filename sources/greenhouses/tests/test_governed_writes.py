"""Boundary regressions for the migrated greenhouses domain writers.

Each case pins one ungoverned-write finding to the shared mutation boundary:
denied actors write nothing and bump no parent revision; allowed writes run
inside the parent's ``content_mutation`` and record the governed revision
bump and audit event on the Greenhouse root.
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from materials.models import (
    Material,
    MaterialComponent,
    SampleSeries,
)
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
)
from utils.object_management.models import ReviewAction
from utils.tests.testcases import ViewWithPermissionsTestCase


def _events_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
    )


def _revision(obj):
    return type(obj)._base_manager.get(pk=obj.pk).content_revision


class UpdateGreenhouseGrowthCycleValuesBoundaryTestCase(ViewWithPermissionsTestCase):
    """The values-update route previously had no permission check and
    silently reassigned ``owner`` to the request user on every save. The
    cycle is an owned child: the governed update decides edit on its
    Greenhouse root and never rewrites ownership."""

    member_permissions = "change_greenhouse"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner, name="GW Greenhouse", publication_status="private"
        )
        cls.cycle = GreenhouseGrowthCycle.objects.create(
            owner=cls.owner, greenhouse=cls.greenhouse, cycle_number=1
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_greenhouse")
        )

    def url(self):
        return reverse(
            "greenhouse_growth_cycle_update_values",
            kwargs={"pk": self.greenhouse.pk, "cycle_pk": self.cycle.pk},
        )

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 403)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.owner, self.owner)

    def test_post_denied_for_outsider_keeps_owner_and_values(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 403)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.owner, self.owner)
        self.assertEqual(self.cycle.cycle_number, 1)

    def test_post_denied_on_published_greenhouse(self):
        self.greenhouse.publication_status = "published"
        self.greenhouse.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 403)

    def test_post_authorized_redirects_without_owner_change(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("greenhouse-detail", kwargs={"pk": self.greenhouse.pk}),
        )
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.owner, self.owner)


class GrowthCycleModalCreateBoundaryTestCase(ViewWithPermissionsTestCase):
    """The modal create gate is the central owned-child create decision on
    the URL greenhouse; the cycle, its timestep sets, and the cycle
    ordering write inside one ``content_mutation`` on the parent."""

    member_permissions = "change_greenhouse"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.member, name="GW Greenhouse", publication_status="private"
        )
        material = Material.objects.create(name="GW Crop residue")
        cls.residue = SampleSeries.objects.create(
            owner=cls.member, material=material, name="GW Residue"
        )
        cls.culture = Culture.objects.create(
            owner=cls.member, name="GW Crop", residue=cls.residue
        )
        distribution, _ = TemporalDistribution.objects.get_or_create(
            name="Months of the year"
        )
        cls.timestep, _ = Timestep.objects.get_or_create(
            name="January", distribution=distribution
        )

    def url(self, greenhouse=None):
        return reverse(
            "greenhousegrowthcycle-create",
            kwargs={"pk": (greenhouse or self.greenhouse).pk},
        )

    def post_data(self):
        return {"culture": self.culture.pk, "timesteps": [self.timestep.pk]}

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        revision = _revision(self.greenhouse)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())
        self.assertEqual(_revision(self.greenhouse), revision)

    def test_post_denied_for_member_on_foreign_greenhouse(self):
        foreign = Greenhouse.objects.create(
            owner=self.owner, name="Foreign", publication_status="private"
        )
        self.client.force_login(self.member)
        response = self.client.post(self.url(foreign), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_post_authorized_creates_cycle_inside_parent_boundary(self):
        self.client.force_login(self.member)
        revision = _revision(self.greenhouse)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        cycle = GreenhouseGrowthCycle.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(cycle.owner, self.member)
        self.assertEqual(cycle.culture, self.culture)
        self.assertTrue(
            GrowthTimeStepSet.objects.filter(
                growth_cycle=cycle, timestep=self.timestep
            ).exists()
        )
        self.assertEqual(_revision(self.greenhouse), revision + 1)
        self.assertTrue(
            _events_for(self.greenhouse)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.member)
            .exists()
        )


class GrowthTimeStepSetModalUpdateBoundaryTestCase(ViewWithPermissionsTestCase):
    """The timestep-set modal edits owned share rows: the form and inline
    formset save inside one ``content_mutation`` on the Greenhouse root,
    so the parent's snapshot diff records revision and audit."""

    member_permissions = "change_greenhouse"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner, name="GW Greenhouse", publication_status="private"
        )
        cls.cycle = GreenhouseGrowthCycle.objects.create(
            owner=cls.owner, greenhouse=cls.greenhouse, cycle_number=1
        )
        distribution = TemporalDistribution.objects.create(
            owner=cls.owner, name="GW Distribution"
        )
        cls.timestep = Timestep.objects.create(
            owner=cls.owner, name="GW Timestep", distribution=distribution
        )
        cls.timestepset = GrowthTimeStepSet.objects.create(
            owner=cls.owner,
            growth_cycle=cls.cycle,
            timestep=cls.timestep,
        )
        cls.component = MaterialComponent.objects.create(
            name="GW Component", publication_status="published"
        )
        cls.share = GrowthShare.objects.create(
            owner=cls.owner,
            component=cls.component,
            timestepset=cls.timestepset,
            average=1.0,
            standard_deviation=0.1,
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_greenhouse")
        )

    def url(self):
        return reverse(
            "greenhousegrowthcycle-timestep-update-modal",
            kwargs={"pk": self.timestepset.pk},
        )

    def post_data(self, average="7.5"):
        return {
            "growthshare_set-TOTAL_FORMS": "1",
            "growthshare_set-INITIAL_FORMS": "1",
            "growthshare_set-MIN_NUM_FORMS": "0",
            "growthshare_set-MAX_NUM_FORMS": "1000",
            "growthshare_set-0-id": str(self.share.pk),
            "growthshare_set-0-component": str(self.component.pk),
            "growthshare_set-0-average": average,
            "growthshare_set-0-standard_deviation": "0.3",
        }

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.greenhouse)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.share.refresh_from_db()
        self.assertEqual(self.share.average, 1.0)
        self.assertEqual(_revision(self.greenhouse), revision)

    def test_post_authorized_saves_shares_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.greenhouse)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        self.share.refresh_from_db()
        self.assertEqual(self.share.average, 7.5)
        self.assertEqual(_revision(self.greenhouse), revision + 1)
        self.assertTrue(
            _events_for(self.greenhouse)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )
