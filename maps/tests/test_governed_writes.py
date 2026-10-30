"""Boundary regressions for the migrated maps domain writers.

The merge-LAU catchment flow creates a sibling Region root and the
catchment's region linkage inside the same authorized create boundary;
detail views scope embedded attribute values by read visibility.
"""

from datetime import date

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse

from maps.models import (
    Catchment,
    GeoPolygon,
    LauRegion,
    Region,
    RegionAttributeValue,
    RegionProperty,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Unit
from utils.tests.testcases import ViewWithPermissionsTestCase


def _events_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
    )


class CatchmentCreateMergeLauBoundaryTestCase(ViewWithPermissionsTestCase):
    """The compound create writes Catchment + sibling Region + GeoPolygon +
    ``composed_of`` edges inside one authorized boundary: the Region needs
    its own create capability, gets ``owner=actor`` and a ``created`` audit
    event, and the catchment linkage persists inside the same atomic."""

    member_permissions = ["add_catchment", "add_region"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lau_1 = LauRegion.objects.create(
            name="GW Lau 1",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 2), (2, 2), (2, 0), (0, 0))))
            ),
            publication_status="published",
        )
        cls.lau_2 = LauRegion.objects.create(
            name="GW Lau 2",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 2), (0, 4), (2, 4), (2, 2), (0, 2))))
            ),
            publication_status="published",
        )
        cls.parent_region = Region.objects.create(
            name="GW Parent", publication_status="published"
        )

    def post_data(self):
        return {
            "name": "GW Merged Catchment",
            "parent_region": self.parent_region.pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": self.lau_1.region_ptr.pk,
            "form-1-region": self.lau_2.region_ptr.pk,
        }

    def url(self):
        return reverse("catchment-create-merge-lau")

    def test_post_denied_without_region_create_capability_rolls_back(self):
        self.member.user_permissions.clear()
        self.member.user_permissions.add(
            Permission.objects.get(codename="add_catchment")
        )
        self.client.force_login(self.member)
        region_count = Region.objects.count()
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Catchment.objects.filter(name="GW Merged Catchment").exists())
        self.assertEqual(Region.objects.count(), region_count)

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Catchment.objects.filter(name="GW Merged Catchment").exists())

    def test_post_authorized_creates_catchment_and_owned_region_with_audit(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        catchment = Catchment.objects.get(name="GW Merged Catchment")
        self.assertEqual(catchment.owner, self.member)
        self.assertIsNotNone(catchment.region)
        region = catchment.region
        # The sibling region is a governed root of its own: attributed to
        # the actor and audited inside the same boundary.
        self.assertEqual(region.owner, self.member)
        self.assertCountEqual(
            region.composed_of.all(),
            [self.lau_1.region_ptr, self.lau_2.region_ptr],
        )
        self.assertTrue(
            _events_for(catchment)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        self.assertTrue(
            _events_for(region)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )


class RegionAttributeValueVisibilityTestCase(ViewWithPermissionsTestCase):
    """Region and catchment detail pages must not leak private
    RegionAttributeValue rows: context data is scoped by read visibility."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(
            name="GW Region", publication_status="published"
        )
        cls.catchment = Catchment.objects.create(
            name="GW Catchment",
            region=cls.region,
            publication_status="published",
        )
        cls.property = RegionProperty.objects.create(
            owner=cls.owner, name="GW Property", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            owner=cls.owner, name="GW Unit", publication_status="published"
        )
        cls.published_value = RegionAttributeValue.objects.create(
            owner=cls.owner,
            region=cls.region,
            property=cls.property,
            unit=cls.unit,
            value=1.0,
            date=date(2024, 1, 1),
            publication_status="published",
        )
        cls.private_value = RegionAttributeValue.objects.create(
            owner=cls.owner,
            region=cls.region,
            property=cls.property,
            unit=cls.unit,
            value=2.0,
            date=date(2024, 2, 1),
            publication_status="private",
        )

    def _context_values(self, response):
        return set(response.context["region_attribute_values"])

    def test_region_detail_scopes_private_values_for_anonymous(self):
        response = self.client.get(
            reverse("region-detail", kwargs={"pk": self.region.pk})
        )
        self.assertEqual(response.status_code, 200)
        values = self._context_values(response)
        self.assertIn(self.published_value, values)
        self.assertNotIn(self.private_value, values)

    def test_region_detail_scopes_private_values_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("region-detail", kwargs={"pk": self.region.pk})
        )
        values = self._context_values(response)
        self.assertIn(self.published_value, values)
        self.assertNotIn(self.private_value, values)

    def test_region_detail_shows_own_private_values_to_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("region-detail", kwargs={"pk": self.region.pk})
        )
        values = self._context_values(response)
        self.assertIn(self.published_value, values)
        self.assertIn(self.private_value, values)

    def test_catchment_detail_scopes_private_values_for_anonymous(self):
        response = self.client.get(
            reverse("catchment-detail", kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 200)
        values = self._context_values(response)
        self.assertIn(self.published_value, values)
        self.assertNotIn(self.private_value, values)
