import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db.models.signals import post_save
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from maps.models import Location, Region
from utils.object_management.models import ReviewAction
from utils.properties.models import Unit
from utils.tests.testcases import ViewSetWithPermissionsTestCase

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleGroup,
    SampleSeries,
)
from ..serializers import (
    CompositionAPISerializer,
    MaterialAPISerializer,
    MaterialPropertyValueWriteSerializer,
    SampleAPISerializer,
    SampleGroupWriteSerializer,
    SampleSeriesAPISerializer,
    SampleWriteSerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JSON = "application/json"


def _make_editor(username, *codenames):
    """Create a user holding only the given direct materials permissions."""
    user = User.objects.create_user(username=username)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="materials", codename__in=codenames
        )
    )
    user.groups.clear()
    return user


class MaterialViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_material",
        "add_material",
        "change_material",
        "delete_material",
    )
    published_material = None
    private_material = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published_material = Material.objects.create(
            name="Published Material", owner=cls.owner, publication_status="published"
        )
        cls.private_material = Material.objects.create(
            name="Private Material", owner=cls.owner, publication_status="private"
        )
        cls.published_component = MaterialComponent.objects.create(
            name="Published Component",
            owner=cls.owner,
            publication_status="published",
        )

    def _list_names(self, response):
        return [item["name"] for item in response.data]

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-material-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_only_published_for_anonymous_user(self):
        response = self.client.get(reverse("api-material-list"))
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertNotIn(self.private_material.name, names)

    def test_get_list_excludes_components(self):
        response = self.client.get(reverse("api-material-list"))

        self.assertNotIn(self.published_component.name, self._list_names(response))

    def test_get_detail_returns_404_for_component(self):
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_component.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-material-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_only_published_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-material-list"))
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertNotIn(self.private_material.name, names)

    def test_get_list_returns_own_private_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-material-list") + "?scope=private")
        names = self._list_names(response)
        self.assertIn(self.private_material.name, names)

    def test_get_list_returns_default_union_for_administrator(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("api-material-list"))
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertIn(self.private_material.name, names)

    def test_get_list_bogus_scope_returns_empty(self):
        """Unknown scopes fail closed for every actor, including admins."""
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("api-material-list") + "?scope=does-not-exist"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk})
        )
        serializer = MaterialAPISerializer(self.published_material)
        self.assertEqual(response.data, serializer.data)

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-material-list"),
            data=json.dumps({"name": "New Material"}),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_403_for_outsider_without_add_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("api-material-list"),
            data=json.dumps({"name": "New Material"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-material-list"),
            data=json.dumps({"name": "Created By Member"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Material.objects.filter(
                name="Created By Member", owner=self.member
            ).exists()
        )

    # --- update ---

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk}),
            data=json.dumps({"name": "Updated Name"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_material.refresh_from_db()
        self.assertEqual(self.private_material.name, "Updated Name")

    def test_patch_http_403_for_owner_without_change_capability(self):
        """Ownership alone does not permit writes: an owner stripped of every
        direct and group capability is denied."""
        self.owner.user_permissions.clear()
        self.owner.groups.clear()
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)
        self.private_material.refresh_from_db()
        self.assertEqual(self.private_material.name, "Private Material")

    def test_patch_http_403_for_owner_on_published(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk}),
            data=json.dumps({"name": "Should Not Work"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

    # --- delete ---

    def test_delete_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.delete(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = Material.objects.create(
            name="To Delete", owner=self.owner, publication_status="private"
        )
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-material-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Material.objects.filter(pk=to_delete.pk).exists())


class SampleSeriesViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_sampleseries",
        "add_sampleseries",
        "change_sampleseries",
        "delete_sampleseries",
    )
    material = None
    published_series = None
    private_series = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="Test Material", owner=cls.owner, publication_status="published"
        )
        cls.published_series = SampleSeries.objects.create(
            material=cls.material,
            name="Published Series",
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_series = SampleSeries.objects.create(
            material=cls.material,
            name="Private Series",
            owner=cls.owner,
            publication_status="private",
        )

    def _list_sample_counts(self, response):
        return len(response.data)

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_anonymous_excludes_private(self):
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._list_sample_counts(response), 1)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_outsider_excludes_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(self._list_sample_counts(response), 1)

    def test_get_list_count_for_owner_includes_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-sampleseries-list") + "?scope=private")
        self.assertEqual(self._list_sample_counts(response), 2)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.published_series.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.published_series.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.published_series.pk})
        )
        serializer = SampleSeriesAPISerializer(self.published_series)
        self.assertEqual(response.data, serializer.data)

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-sampleseries-list"),
            data=json.dumps({"name": "New Series", "material": self.material.pk}),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-sampleseries-list"),
            data=json.dumps({"name": "Member Series", "material": self.material.pk}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            SampleSeries.objects.filter(
                name="Member Series", owner=self.member
            ).exists()
        )

    # --- update ---

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk}),
            data=json.dumps({"name": "Updated Series"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_series.refresh_from_db()
        self.assertEqual(self.private_series.name, "Updated Series")

    # --- delete ---

    def test_delete_http_403_for_owner_with_default_samples(self):
        """The post_save default temporal distribution creates child Samples,
        so deleting this series would cascade across independent reviewable
        children and is denied."""
        to_delete = SampleSeries.objects.create(
            name="To Delete Series",
            material=self.material,
            owner=self.owner,
            publication_status="private",
        )
        child_sample_ids = list(
            Sample.objects.filter(series=to_delete).values_list("pk", flat=True)
        )
        self.assertTrue(child_sample_ids)
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-sampleseries-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SampleSeries.objects.filter(pk=to_delete.pk).exists())
        self.assertEqual(
            set(
                Sample.objects.filter(pk__in=child_sample_ids).values_list(
                    "pk", flat=True
                )
            ),
            set(child_sample_ids),
        )

    def test_delete_http_204_for_owner_on_private(self):
        """A bare series without independent child Samples is deletable."""
        with mute_signals(post_save):
            to_delete = SampleSeries.objects.create(
                name="To Delete Series",
                material=self.material,
                owner=self.owner,
                publication_status="private",
            )
        self.assertFalse(Sample.objects.filter(series=to_delete).exists())
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-sampleseries-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SampleSeries.objects.filter(pk=to_delete.pk).exists())


class SampleViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ("view_sample", "add_sample", "change_sample", "delete_sample")
    material = None
    series = None
    published_sample = None
    private_sample = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="Test Material", owner=cls.owner, publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            material=cls.material,
            name="Test Series",
            owner=cls.owner,
            publication_status="published",
        )
        cls.published_sample = Sample.objects.create(
            series=cls.series,
            material=cls.material,
            name="Published Sample",
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_sample = Sample.objects.create(
            series=cls.series,
            material=cls.material,
            name="Private Sample",
            owner=cls.owner,
            publication_status="private",
        )

    def _list_names(self, response):
        return [item["name"] for item in response.data]

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-sample-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_only_published_for_anonymous_user(self):
        response = self.client.get(reverse("api-sample-list"))
        names = self._list_names(response)
        self.assertIn(self.published_sample.name, names)
        self.assertNotIn(self.private_sample.name, names)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sample-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_only_published_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sample-list"))
        names = self._list_names(response)
        self.assertIn(self.published_sample.name, names)
        self.assertNotIn(self.private_sample.name, names)

    def test_get_list_returns_own_private_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-sample-list") + "?scope=private")
        names = self._list_names(response)
        self.assertIn(self.private_sample.name, names)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.published_sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.published_sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.published_sample.pk})
        )
        serializer = SampleAPISerializer(self.published_sample)
        self.assertEqual(response.data, serializer.data)

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-sample-list"),
            data=json.dumps(
                {"name": "New Sample", "material": self.material.pk, "standalone": True}
            ),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-sample-list"),
            data=json.dumps(
                {
                    "name": "Member Sample",
                    "material": self.material.pk,
                    "standalone": True,
                }
            ),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Sample.objects.filter(name="Member Sample", owner=self.member).exists()
        )

    # --- update ---

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk}),
            data=json.dumps({"name": "Updated Sample"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_sample.refresh_from_db()
        self.assertEqual(self.private_sample.name, "Updated Sample")

    # --- delete ---

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = Sample.objects.create(
            name="To Delete Sample",
            material=self.material,
            standalone=True,
            owner=self.owner,
            publication_status="private",
        )
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-sample-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Sample.objects.filter(pk=to_delete.pk).exists())

    # --- geographic referencing ---

    def test_get_detail_exposes_location_region_and_site(self):
        region = Region.objects.create(
            name="Brittany", country="FR", publication_status="published"
        )
        site = Location.objects.create(name="Viaverda", publication_status="published")
        self.published_sample.location = "Somewhere in Brittany"
        self.published_sample.region = region
        self.published_sample.site = site
        self.published_sample.save()
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.published_sample.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["location"], "Somewhere in Brittany")
        self.assertEqual(response.data["region"], str(region))
        self.assertEqual(response.data["site"], str(site))

    def test_get_list_filters_by_region(self):
        region = Region.objects.create(
            name="Brittany", country="FR", publication_status="published"
        )
        other_region = Region.objects.create(
            name="Hamburg", country="DE", publication_status="published"
        )
        self.published_sample.region = region
        self.published_sample.save()
        Sample.objects.create(
            name="Hamburg Sample",
            material=self.material,
            standalone=True,
            owner=self.owner,
            region=other_region,
            publication_status="published",
        )
        response = self.client.get(reverse("api-sample-list") + f"?region={region.pk}")
        names = self._list_names(response)
        self.assertIn(self.published_sample.name, names)
        self.assertNotIn("Hamburg Sample", names)

    def test_get_list_filters_by_site(self):
        site = Location.objects.create(name="Viaverda", publication_status="published")
        other_site = Location.objects.create(
            name="TUHH campus", publication_status="published"
        )
        self.published_sample.site = site
        self.published_sample.save()
        Sample.objects.create(
            name="TUHH Sample",
            material=self.material,
            standalone=True,
            owner=self.owner,
            site=other_site,
            publication_status="published",
        )
        response = self.client.get(reverse("api-sample-list") + f"?site={site.pk}")
        names = self._list_names(response)
        self.assertIn(self.published_sample.name, names)
        self.assertNotIn("TUHH Sample", names)

    def test_patch_assigns_region_and_site(self):
        region = Region.objects.create(
            name="Brittany", country="FR", publication_status="published"
        )
        site = Location.objects.create(name="Viaverda", publication_status="published")
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk}),
            data=json.dumps({"region": region.pk, "site": site.pk}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.private_sample.refresh_from_db()
        self.assertEqual(self.private_sample.region_id, region.pk)
        self.assertEqual(self.private_sample.site_id, site.pk)

    def test_patch_rejects_inaccessible_region_and_site(self):
        hidden_region = Region.objects.create(
            name="Hidden", country="FR", owner=self.outsider
        )
        hidden_site = Location.objects.create(name="Hidden site", owner=self.outsider)
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk}),
            data=json.dumps({"region": hidden_region.pk, "site": hidden_site.pk}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 400)


class CompositionViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_composition",
        "add_composition",
        "change_composition",
        "delete_composition",
        "change_sample",
    )
    material = None
    series = None
    sample = None
    published_composition = None
    private_composition = None
    group = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="Test Material", owner=cls.owner, publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            material=cls.material,
            name="Test Series",
            owner=cls.owner,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            series=cls.series,
            material=cls.material,
            name="Test Sample",
            owner=cls.owner,
            publication_status="published",
        )
        cls.member_sample = Sample.objects.create(
            material=cls.material,
            name="Member Composition Sample",
            owner=cls.member,
            standalone=True,
            publication_status="private",
        )
        cls.group = MaterialComponentGroup.objects.create(
            name="Test Component Group", publication_status="published"
        )
        cls.published_composition = Composition.objects.create(
            name="Published Composition",
            sample=cls.sample,
            group=cls.group,
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_parent_sample = Sample.objects.create(
            material=cls.material,
            name="Private Parent Sample",
            owner=cls.owner,
            standalone=True,
            publication_status="private",
        )
        cls.private_parent_group = MaterialComponentGroup.objects.create(
            name="Private Parent Group", publication_status="published"
        )
        cls.private_composition = Composition.objects.create(
            name="Private Composition",
            sample=cls.private_parent_sample,
            group=cls.private_parent_group,
            owner=cls.owner,
            publication_status="private",
        )

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_anonymous_excludes_private(self):
        visible_qs = Composition.objects.filter(sample=self.sample)
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)
        payload = (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )
        # The API payload carries no id; the private row is distinguishable
        # only via its dedicated group name.
        self.assertEqual(len(payload), visible_qs.count())
        group_names = {item["group"] for item in payload}
        self.assertIn("Test Component Group", group_names)
        self.assertNotIn("Private Parent Group", group_names)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_outsider_excludes_private(self):
        visible_qs = Composition.objects.filter(sample=self.sample)
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)
        payload = (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )
        # The API payload carries no id; the private row is distinguishable
        # only via its dedicated group name.
        self.assertEqual(len(payload), visible_qs.count())
        group_names = {item["group"] for item in payload}
        self.assertIn("Test Component Group", group_names)
        self.assertNotIn("Private Parent Group", group_names)

    def test_get_list_count_for_owner_includes_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-composition-list") + "?scope=private")
        # Owner sees at least both the published and private compositions created in
        # setUp. The signal-created default composition may add extra rows.
        self.assertGreaterEqual(len(response.data), 2)

    def test_private_composition_stays_hidden_when_itself_published(self):
        """Owned-child status is not authoritative for visibility: publishing
        the private composition while its parent sample stays private must
        not expose it."""
        self.private_composition.publication_status = "published"
        self.private_composition.save()
        response = self.client.get(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.published_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_anonymous_on_private(self):
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.private_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.published_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.private_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.private_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.published_composition.pk}
            )
        )
        serializer = CompositionAPISerializer(self.published_composition)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_uses_raw_derived_normalized_shares(self):
        percent_unit = Unit.objects.filter(name="%").first()
        if percent_unit is None:
            percent_unit = Unit.objects.create(name="%", symbol="percent")
        carbon = MaterialComponent.objects.create(name="Carbon")
        nitrogen = MaterialComponent.objects.create(name="Nitrogen")
        ComponentMeasurement.objects.create(
            sample=self.sample,
            group=self.group,
            component=carbon,
            unit=percent_unit,
            average=Decimal("40"),
        )
        ComponentMeasurement.objects.create(
            sample=self.sample,
            group=self.group,
            component=nitrogen,
            unit=percent_unit,
            average=Decimal("60"),
        )

        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.published_composition.pk},
            )
        )

        self.assertEqual(
            response.data["shares"],
            [
                {
                    "component": "Nitrogen",
                    "average": 0.6,
                    "standard_deviation": None,
                },
                {
                    "component": "Carbon",
                    "average": 0.4,
                    "standard_deviation": None,
                },
            ],
        )

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps({"sample": self.sample.pk, "group": self.group.pk}),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_403_for_member_targeting_another_users_sample(self):
        extra_group = MaterialComponentGroup.objects.create(
            name="Unauthorized Composition Group"
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps({"sample": self.sample.pk, "group": extra_group.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)

    def test_post_http_201_for_member_with_add_permission(self):
        extra_group = MaterialComponentGroup.objects.create(
            name="Extra Group For Composition", publication_status="published"
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps({"sample": self.member_sample.pk, "group": extra_group.pk}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Composition.objects.filter(
                sample=self.member_sample, group=extra_group, owner=self.member
            ).exists()
        )

    def test_post_http_201_for_editor_with_edit_grant_on_private_sample(self):
        """Owned children resolve through parent edit: an editor with a
        direct grant and ``change_sample`` may add compositions without
        owning the sample or holding ``add_composition``."""
        editor = _make_editor(
            "composition-editor", "change_sample", "change_composition"
        )
        self.private_parent_sample.add_editor(editor, granted_by=self.owner)
        extra_group = MaterialComponentGroup.objects.create(
            name="Editor Composition Group", publication_status="published"
        )
        self.client.force_login(editor)

        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps(
                {"sample": self.private_parent_sample.pk, "group": extra_group.pk}
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Composition.objects.filter(
                sample=self.private_parent_sample,
                group=extra_group,
                owner=editor,
            ).exists()
        )

    def test_post_http_403_for_sample_owner_without_change_sample(self):
        """Ownership and add capability alone are not enough: the actor must
        still be able to edit the parent sample."""
        no_change_owner = _make_editor(
            "no-change-owner", "add_composition", "change_composition"
        )
        sample = Sample.objects.create(
            material=self.material,
            name="No-change owner's sample",
            owner=no_change_owner,
            standalone=True,
            publication_status="private",
        )
        extra_group = MaterialComponentGroup.objects.create(
            name="No-change Group", publication_status="published"
        )
        self.client.force_login(no_change_owner)

        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps({"sample": sample.pk, "group": extra_group.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Composition.objects.filter(sample=sample, group=extra_group).exists()
        )

    # --- update ---

    def test_patch_http_200_for_editor_reparenting_between_granted_samples(self):
        """Reparenting an owned child re-checks both parents: an editor with
        grants on the source and target samples may move a composition."""
        editor = _make_editor("reparent-editor", "change_sample", "change_composition")
        target_sample = Sample.objects.create(
            material=self.material,
            name="Reparent Target Sample",
            owner=self.owner,
            standalone=True,
            publication_status="private",
        )
        self.private_parent_sample.add_editor(editor, granted_by=self.owner)
        target_sample.add_editor(editor, granted_by=self.owner)
        self.client.force_login(editor)

        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"sample": target_sample.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 200)
        self.private_composition.refresh_from_db()
        self.assertEqual(self.private_composition.sample, target_sample)

    def test_patch_http_403_for_editor_reparenting_to_ungranted_sample(self):
        editor = _make_editor(
            "reparent-denied-editor", "change_sample", "change_composition"
        )
        self.private_parent_sample.add_editor(editor, granted_by=self.owner)
        self.client.force_login(editor)

        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"sample": self.member_sample.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.private_composition.refresh_from_db()
        self.assertEqual(self.private_composition.sample, self.private_parent_sample)

    def test_patch_http_403_when_owner_targets_another_users_sample(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"sample": self.member_sample.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.private_composition.refresh_from_db()
        self.assertEqual(self.private_composition.sample, self.private_parent_sample)

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"order": 50}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"order": 50}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_composition.refresh_from_db()
        self.assertEqual(self.private_composition.order, 50)


class ComponentMeasurementViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "change_sample",
        "view_componentmeasurement",
        "add_componentmeasurement",
        "change_componentmeasurement",
        "delete_componentmeasurement",
    )
    material = None
    series = None
    sample = None
    group = None
    component = None
    unit = None
    published_measurement = None
    private_measurement = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="CM Test Material", owner=cls.owner, publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            material=cls.material,
            name="CM Test Series",
            owner=cls.owner,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            series=cls.series,
            material=cls.material,
            name="CM Test Sample",
            owner=cls.owner,
            publication_status="published",
        )
        cls.member_sample = Sample.objects.create(
            material=cls.material,
            name="Member Measurement Sample",
            owner=cls.member,
            standalone=True,
            publication_status="private",
        )
        cls.group = MaterialComponentGroup.objects.create(
            name="CM Test Group", publication_status="published"
        )
        cls.component = MaterialComponent.objects.create(
            name="CM Test Component", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="g/kg", symbol="g/kg", publication_status="published"
        )
        cls.published_measurement = ComponentMeasurement.objects.create(
            sample=cls.sample,
            group=cls.group,
            component=cls.component,
            unit=cls.unit,
            average=Decimal("10"),
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_measurement = ComponentMeasurement.objects.create(
            sample=cls.sample,
            group=cls.group,
            component=cls.component,
            unit=cls.unit,
            average=Decimal("20"),
            owner=cls.owner,
            publication_status="private",
        )

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-componentmeasurement-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_excludes_private_for_anonymous(self):
        response = self.client.get(reverse("api-componentmeasurement-list"))
        averages = [Decimal(item["average"]) for item in response.data]
        self.assertIn(self.published_measurement.average, averages)
        self.assertNotIn(self.private_measurement.average, averages)

    def test_get_list_excludes_private_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-componentmeasurement-list"))
        averages = [Decimal(item["average"]) for item in response.data]
        self.assertNotIn(self.private_measurement.average, averages)

    def test_get_list_includes_own_private_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-componentmeasurement-list") + "?scope=private"
        )
        pks = [item["id"] for item in response.data]
        self.assertIn(self.private_measurement.pk, pks)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.published_measurement.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-componentmeasurement-list"),
            data=json.dumps(
                {
                    "sample": self.sample.pk,
                    "group": self.group.pk,
                    "component": self.component.pk,
                    "unit": self.unit.pk,
                    "average": "5.0",
                }
            ),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_403_for_member_targeting_another_users_sample(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("api-componentmeasurement-list"),
            data=json.dumps(
                {
                    "sample": self.sample.pk,
                    "group": self.group.pk,
                    "component": self.component.pk,
                    "unit": self.unit.pk,
                    "average": "5.0",
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-componentmeasurement-list"),
            data=json.dumps(
                {
                    "sample": self.member_sample.pk,
                    "group": self.group.pk,
                    "component": self.component.pk,
                    "unit": self.unit.pk,
                    "average": "5.0",
                }
            ),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ComponentMeasurement.objects.filter(
                sample=self.member_sample,
                component=self.component,
                average=Decimal("5.0"),
                owner=self.member,
            ).exists()
        )

    def test_post_http_403_for_editor_without_add_permission(self):
        """Independent evidence needs its own add capability: a parent edit
        grant alone must not let an editor attach measurements."""
        editor = _make_editor(
            "cm-editor-no-add", "change_sample", "change_componentmeasurement"
        )
        self.member_sample.add_editor(editor, granted_by=self.member)
        self.client.force_login(editor)

        response = self.client.post(
            reverse("api-componentmeasurement-list"),
            data=json.dumps(
                {
                    "sample": self.member_sample.pk,
                    "group": self.group.pk,
                    "component": self.component.pk,
                    "unit": self.unit.pk,
                    "average": "7.5",
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ComponentMeasurement.objects.filter(
                sample=self.member_sample, owner=editor
            ).exists()
        )

    def test_post_http_201_for_editor_with_add_permission_and_grant(self):
        """With both the add capability and a parent edit grant, an editor
        may attach independent evidence to a sample they do not own."""
        editor = _make_editor(
            "cm-editor",
            "change_sample",
            "add_componentmeasurement",
            "change_componentmeasurement",
        )
        self.member_sample.add_editor(editor, granted_by=self.member)
        self.client.force_login(editor)

        response = self.client.post(
            reverse("api-componentmeasurement-list"),
            data=json.dumps(
                {
                    "sample": self.member_sample.pk,
                    "group": self.group.pk,
                    "component": self.component.pk,
                    "unit": self.unit.pk,
                    "average": "7.5",
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ComponentMeasurement.objects.filter(
                sample=self.member_sample,
                component=self.component,
                average=Decimal("7.5"),
                owner=editor,
            ).exists()
        )

    # --- update ---

    def test_patch_http_403_when_owner_targets_another_users_sample(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            ),
            data=json.dumps({"sample": self.member_sample.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.private_measurement.refresh_from_db()
        self.assertEqual(self.private_measurement.sample, self.sample)

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            ),
            data=json.dumps({"average": "99.0"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            ),
            data=json.dumps({"average": "25.0"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_measurement.refresh_from_db()
        self.assertEqual(self.private_measurement.average, Decimal("25.0"))

    # --- delete ---

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = ComponentMeasurement.objects.create(
            sample=self.sample,
            group=self.group,
            component=self.component,
            unit=self.unit,
            average=Decimal("1"),
            owner=self.owner,
            publication_status="private",
        )
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-componentmeasurement-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ComponentMeasurement.objects.filter(pk=to_delete.pk).exists())


class MaterialPropertyValueViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "change_sample",
        "view_materialpropertyvalue",
        "add_materialpropertyvalue",
        "change_materialpropertyvalue",
        "delete_materialpropertyvalue",
    )
    material = None
    series = None
    sample = None
    prop = None
    unit = None
    published_value = None
    private_value = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="MPV Test Material", owner=cls.owner, publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            material=cls.material,
            name="MPV Test Series",
            owner=cls.owner,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            series=cls.series,
            material=cls.material,
            name="MPV Test Sample",
            owner=cls.owner,
            publication_status="published",
        )
        cls.member_sample = Sample.objects.create(
            material=cls.material,
            name="Member Property Sample",
            owner=cls.member,
            standalone=True,
            publication_status="private",
        )
        cls.prop = MaterialProperty.objects.create(
            name="MPV Test Property",
            owner=cls.owner,
            publication_status="published",
        )
        cls.unit = Unit.objects.create(
            name="MPV Test Unit", symbol="mpvu", publication_status="published"
        )
        cls.published_value = MaterialPropertyValue.objects.create(
            sample=cls.sample,
            property=cls.prop,
            unit=cls.unit,
            average=Decimal("100"),
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_value = MaterialPropertyValue.objects.create(
            sample=cls.sample,
            property=cls.prop,
            unit=cls.unit,
            average=Decimal("200"),
            owner=cls.owner,
            publication_status="private",
        )

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-materialpropertyvalue-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_excludes_private_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-materialpropertyvalue-list"))
        pks = [item["id"] for item in response.data]
        self.assertIn(self.published_value.pk, pks)
        self.assertNotIn(self.private_value.pk, pks)

    def test_get_list_includes_own_private_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-materialpropertyvalue-list") + "?scope=private"
        )
        pks = [item["id"] for item in response.data]
        self.assertIn(self.private_value.pk, pks)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.published_value.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.private_value.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.private_value.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    # --- create ---

    def test_post_http_403_for_member_targeting_another_users_sample(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("api-materialpropertyvalue-list"),
            data=json.dumps(
                {
                    "sample": self.sample.pk,
                    "property": self.prop.pk,
                    "unit": self.unit.pk,
                    "average": "50.0",
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-materialpropertyvalue-list"),
            data=json.dumps(
                {
                    "sample": self.member_sample.pk,
                    "property": self.prop.pk,
                    "unit": self.unit.pk,
                    "average": "50.0",
                }
            ),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            MaterialPropertyValue.objects.filter(
                sample=self.member_sample,
                property=self.prop,
                average=Decimal("50.0"),
                owner=self.member,
            ).exists()
        )

    def test_post_http_201_without_sample(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("api-materialpropertyvalue-list"),
            data=json.dumps(
                {
                    "property": self.prop.pk,
                    "unit": self.unit.pk,
                    "average": "75.0",
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            MaterialPropertyValue.objects.filter(
                sample__isnull=True,
                property=self.prop,
                average=Decimal("75.0"),
                owner=self.member,
            ).exists()
        )

    def test_post_parent_swap_after_validation_rolls_back(self):
        """A serializer persisting a different parent than the authorized
        context is denied and rolled back entirely — both when a parent was
        authorized and when the authorized context was legitimately absent."""
        swapped = Sample.objects.create(
            material=self.material,
            name="Swapped Sample",
            owner=self.member,
            standalone=True,
        )
        original_create = MaterialPropertyValueWriteSerializer.create
        executed = []

        def poisoned_create(serializer, validated_data):
            validated_data["sample"] = swapped
            executed.append(True)
            return original_create(serializer, validated_data)

        self.client.force_login(self.member)
        for payload in (
            {
                "sample": self.member_sample.pk,
                "property": self.prop.pk,
                "unit": self.unit.pk,
                "average": "50.0",
            },
            {
                "property": self.prop.pk,
                "unit": self.unit.pk,
                "average": "50.0",
            },
        ):
            with self.subTest(sample_supplied="sample" in payload):
                executed.clear()
                with patch.object(
                    MaterialPropertyValueWriteSerializer, "create", poisoned_create
                ):
                    response = self.client.post(
                        reverse("api-materialpropertyvalue-list"),
                        data=json.dumps(payload),
                        content_type=JSON,
                    )
                self.assertTrue(executed, "poisoned create did not run")
                self.assertEqual(response.status_code, 403)
                self.assertFalse(
                    MaterialPropertyValue.objects.filter(
                        property=self.prop, owner=self.member
                    ).exists()
                )
                self.assertFalse(ReviewAction.objects.exists())

    # --- update ---

    def test_patch_http_403_when_owner_targets_another_users_sample(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.private_value.pk},
            ),
            data=json.dumps({"sample": self.member_sample.pk}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 403)
        self.private_value.refresh_from_db()
        self.assertEqual(self.private_value.sample, self.sample)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.private_value.pk},
            ),
            data=json.dumps({"average": "250.0"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_value.refresh_from_db()
        self.assertEqual(self.private_value.average, Decimal("250.0"))

    # --- delete ---

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = MaterialPropertyValue.objects.create(
            sample=self.sample,
            property=self.prop,
            unit=self.unit,
            average=Decimal("1"),
            owner=self.owner,
            publication_status="private",
        )
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-materialpropertyvalue-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MaterialPropertyValue.objects.filter(pk=to_delete.pk).exists())


class SampleGroupViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_samplegroup",
        "add_samplegroup",
        "change_samplegroup",
        "delete_samplegroup",
        "change_sample",
    )
    published_group = None
    private_group = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published_group = SampleGroup.objects.create(
            name="Published Group",
            owner=cls.owner,
            kind="study",
            publication_status="published",
        )
        cls.private_group = SampleGroup.objects.create(
            name="Private Group",
            owner=cls.owner,
            kind="experiment",
            publication_status="private",
        )
        cls.material = Material.objects.create(
            name="Group VS Material",
            owner=cls.owner,
            publication_status="published",
        )
        cls.published_sample = Sample.objects.create(
            name="VS published member",
            material=cls.material,
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_sample = Sample.objects.create(
            name="VS private member",
            material=cls.material,
            owner=cls.owner,
            publication_status="private",
        )
        cls.published_sample.sample_groups.add(cls.published_group)
        cls.private_sample.sample_groups.add(cls.published_group)
        cls.foreign_private_sample = Sample.objects.create(
            name="Foreign private sample",
            material=cls.material,
            owner=cls.outsider,
            publication_status="private",
        )
        with mute_signals(post_save):
            cls.published_source = Source.objects.create(
                title="VS published source",
                owner=cls.owner,
                publication_status="published",
            )
            cls.private_source = Source.objects.create(
                title="VS private source",
                owner=cls.owner,
                publication_status="private",
            )
            cls.foreign_private_source = Source.objects.create(
                title="Foreign private source",
                owner=cls.outsider,
                publication_status="private",
            )
        cls.published_group.sources.add(cls.published_source, cls.private_source)

    def _list_names(self, response):
        return [item["name"] for item in response.data]

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-samplegroup-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_only_published_for_anonymous_user(self):
        response = self.client.get(reverse("api-samplegroup-list"))
        names = self._list_names(response)
        self.assertIn(self.published_group.name, names)
        self.assertNotIn(self.private_group.name, names)

    def test_get_list_returns_only_published_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-samplegroup-list"))
        names = self._list_names(response)
        self.assertIn(self.published_group.name, names)
        self.assertNotIn(self.private_group.name, names)

    def test_get_list_returns_own_private_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-samplegroup-list") + "?scope=private")
        names = self._list_names(response)
        self.assertIn(self.private_group.name, names)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.published_group.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_404_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_get_detail_http_200_ok_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_public_shape(self):
        response = self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.published_group.pk})
        )
        self.assertEqual(
            set(response.data.keys()),
            {"id", "name", "kind", "description", "sources", "samples"},
        )

    def _detail(self, user=None):
        if user is not None:
            self.client.force_login(user)
        return self.client.get(
            reverse("api-samplegroup-detail", kwargs={"pk": self.published_group.pk})
        )

    def test_detail_hides_private_members_and_sources_for_anonymous(self):
        response = self._detail()

        self.assertEqual(response.status_code, 200)
        names = [sample["name"] for sample in response.data["samples"]]
        self.assertEqual(names, ["VS published member"])
        source_pks = [source["pk"] for source in response.data["sources"]]
        self.assertEqual(source_pks, [self.published_source.pk])

    def test_detail_hides_private_members_and_sources_for_outsider(self):
        response = self._detail(self.outsider)

        self.assertEqual(response.status_code, 200)
        names = [sample["name"] for sample in response.data["samples"]]
        self.assertNotIn("VS private member", names)
        source_pks = [source["pk"] for source in response.data["sources"]]
        self.assertNotIn(self.private_source.pk, source_pks)

    def test_detail_shows_private_members_and_sources_for_owner(self):
        response = self._detail(self.owner)

        self.assertEqual(response.status_code, 200)
        names = [sample["name"] for sample in response.data["samples"]]
        self.assertIn("VS private member", names)
        source_pks = [source["pk"] for source in response.data["sources"]]
        self.assertIn(self.private_source.pk, source_pks)

    # --- create ---

    def test_post_http_403_for_unauthenticated(self):
        response = self.client.post(
            reverse("api-samplegroup-list"),
            data=json.dumps({"name": "New Group"}),
            content_type=JSON,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_post_http_201_for_member_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-samplegroup-list"),
            data=json.dumps({"name": "Member Group", "kind": "experiment"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            SampleGroup.objects.filter(name="Member Group", owner=self.member).exists()
        )

    # --- update ---

    def test_patch_http_404_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_http_200_for_owner_on_private(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"name": "Updated Group"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_group.refresh_from_db()
        self.assertEqual(self.private_group.name, "Updated Group")

    def test_patch_samples_sets_membership(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"samples": [self.private_sample.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(self.private_group.samples.all(), [self.private_sample])

    def test_patch_samples_rejects_uneditable_published_sample(self):
        """A staff user without the change_sample capability must not bypass
        edit-scope via the sample-group membership update: public readability
        does not grant membership writes."""
        staff = User.objects.create_user(username="staff-only", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(
                codename="change_samplegroup",
                content_type__app_label="materials",
            )
        )
        self.private_group.add_editor(staff, granted_by=self.owner)
        revision_before = self.private_group.content_revision
        self.client.force_login(staff)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"samples": [self.published_sample.pk]}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 400)
        self.private_group.refresh_from_db()
        self.assertEqual(self.private_group.content_revision, revision_before)
        self.assertNotIn(self.published_sample, self.private_group.samples.all())

    def test_patch_samples_preserves_locked_membership(self):
        """A staff-only grantee cannot detach memberships at all: both the
        private and the published rows remain after clearing samples."""
        staff = User.objects.create_user(username="staff-only", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(
                codename="change_samplegroup",
                content_type__app_label="materials",
            )
        )
        self.private_group.add_editor(staff, granted_by=self.owner)
        self.published_sample.sample_groups.add(self.private_group)
        self.private_sample.sample_groups.add(self.private_group)
        self.client.force_login(staff)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"samples": []}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 200)
        self.private_group.refresh_from_db()
        self.assertCountEqual(
            self.private_group.samples.all(),
            [self.published_sample, self.private_sample],
        )

    def test_patch_samples_rolls_back_when_change_sample_revoked_post_validation(
        self,
    ):
        """If the actor's sample-edit capability is revoked after field
        validation but before the write boundary, the whole PATCH must roll
        back — serializer validation must not substitute for edit
        authorization at write time."""
        original_validate = SampleGroupWriteSerializer.validate_samples
        executed = []
        change_sample = Permission.objects.get(
            codename="change_sample",
            content_type__app_label="materials",
        )

        def revoke_after_validation(serializer, value):
            result = original_validate(serializer, value)
            executed.append(True)
            # Revoke ONLY the direct change_sample permission: the actor's
            # group memberships were stripped before the request, so this
            # leaves them genuinely without the capability while ownership,
            # the root change_samplegroup permission, active status and every
            # other permission stay intact.
            self.owner.user_permissions.remove(change_sample)
            fresh = User.objects.get(pk=self.owner.pk)
            self.assertFalse(
                fresh.has_perm("materials.change_sample"),
                "actor should have lost the direct change capability",
            )
            self.assertTrue(
                fresh.has_perm("materials.change_samplegroup"),
                "root write capability must remain",
            )
            self.assertTrue(fresh.is_active)
            return result

        # Remove group-derived capabilities: the registered role auto-joins
        # new users, so only direct fixture permissions should remain.
        self.owner.groups.clear()
        self.owner = User.objects.get(pk=self.owner.pk)
        revision_before = self.private_group.content_revision
        self.assertTrue(self.owner.has_perm("materials.change_sample"))
        self.client.force_login(self.owner)
        with patch.object(
            SampleGroupWriteSerializer, "validate_samples", revoke_after_validation
        ):
            response = self.client.patch(
                reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
                data=json.dumps(
                    {"name": "Must roll back", "samples": [self.private_sample.pk]}
                ),
                content_type=JSON,
            )
        self.assertTrue(executed, "revoking validator did not run")
        self.private_group.refresh_from_db()
        mutation = (
            f"name={self.private_group.name!r} "
            f"revision={self.private_group.content_revision} "
            f"members={list(self.private_group.samples.all())!r}"
        )
        self.assertEqual(response.status_code, 400, mutation)
        self.assertEqual(self.private_group.name, "Private Group", mutation)
        self.assertEqual(self.private_group.content_revision, revision_before, mutation)
        self.assertNotIn(self.private_sample, self.private_group.samples.all())
        self.assertFalse(ReviewAction.objects.filter(action="edited").exists())

    def test_post_samples_rolls_back_when_change_sample_revoked_post_validation(
        self,
    ):
        """The same mid-flight revocation must abort a create: no group, no
        membership, no audit event."""
        original_validate = SampleGroupWriteSerializer.validate_samples
        executed = []
        change_sample = Permission.objects.get(
            codename="change_sample",
            content_type__app_label="materials",
        )

        def revoke_after_validation(serializer, value):
            result = original_validate(serializer, value)
            executed.append(True)
            self.member.user_permissions.remove(change_sample)
            fresh = User.objects.get(pk=self.member.pk)
            self.assertFalse(
                fresh.has_perm("materials.change_sample"),
                "actor should have lost the direct change capability",
            )
            self.assertTrue(
                fresh.has_perm("materials.add_samplegroup"),
                "root create capability must remain",
            )
            self.assertTrue(fresh.is_active)
            return result

        self.member.groups.clear()
        self.member = User.objects.get(pk=self.member.pk)
        member_sample = Sample.objects.create(
            name="Member revoke sample",
            material=self.material,
            owner=self.member,
            standalone=True,
        )
        self.assertTrue(self.member.has_perm("materials.add_samplegroup"))
        self.assertTrue(self.member.has_perm("materials.change_sample"))
        self.client.force_login(self.member)
        with patch.object(
            SampleGroupWriteSerializer, "validate_samples", revoke_after_validation
        ):
            response = self.client.post(
                reverse("api-samplegroup-list"),
                data=json.dumps(
                    {
                        "name": "Revoked membership group",
                        "kind": "experiment",
                        "samples": [member_sample.pk],
                    }
                ),
                content_type=JSON,
            )
        self.assertTrue(executed, "revoking validator did not run")
        persisted = SampleGroup.objects.filter(name="Revoked membership group").first()
        mutation = (
            f"group={persisted!r} "
            f"members={list(persisted.samples.all()) if persisted else []!r}"
        )
        self.assertEqual(response.status_code, 400, mutation)
        self.assertIsNone(persisted, mutation)
        self.assertFalse(ReviewAction.objects.exists())

    def test_patch_samples_rejects_foreign_private_sample(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"samples": [self.foreign_private_sample.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.foreign_private_sample, self.private_group.samples.all())

    def test_patch_sources_rejects_foreign_private_source(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-samplegroup-detail", kwargs={"pk": self.private_group.pk}),
            data=json.dumps({"sources": [self.foreign_private_source.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.foreign_private_source, self.private_group.sources.all())

    def test_post_create_sets_samples_and_sources(self):
        own_sample = Sample.objects.create(
            name="VS member owned",
            material=self.material,
            owner=self.member,
            publication_status="private",
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-samplegroup-list"),
            data=json.dumps(
                {
                    "name": "Populated Group",
                    "kind": "study",
                    "samples": [own_sample.pk],
                    "sources": [self.published_source.pk],
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 201)
        group = SampleGroup.objects.get(name="Populated Group")
        self.assertCountEqual(group.samples.all(), [own_sample])
        self.assertCountEqual(group.sources.all(), [self.published_source])

    def test_post_create_rejects_other_users_published_sample(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-samplegroup-list"),
            data=json.dumps(
                {
                    "name": "Populated Group",
                    "kind": "study",
                    "samples": [self.published_sample.pk],
                }
            ),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SampleGroup.objects.filter(name="Populated Group").exists())

    # --- delete ---

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = SampleGroup.objects.create(
            name="To Delete Group",
            owner=self.owner,
            publication_status="private",
        )
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-samplegroup-detail", kwargs={"pk": to_delete.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SampleGroup.objects.filter(pk=to_delete.pk).exists())


class SampleViewSetSampleGroupsTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_sample",
        "add_sample",
        "change_sample",
        "change_samplegroup",
    )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            name="Group API Material",
            owner=cls.owner,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            name="Group API Sample",
            material=cls.material,
            owner=cls.owner,
            publication_status="private",
        )
        cls.group = SampleGroup.objects.create(
            name="API Group", kind="study", owner=cls.owner
        )
        cls.foreign_private_group = SampleGroup.objects.create(
            name="Foreign Private Group",
            kind="other",
            owner=cls.outsider,
            publication_status="private",
        )
        cls.foreign_published_group = SampleGroup.objects.create(
            name="Foreign Published Group",
            kind="other",
            owner=cls.outsider,
            publication_status="published",
        )

    def test_sample_detail_reads_compact_groups(self):
        self.sample.sample_groups.add(self.group)
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["sample_groups"]), 1)
        self.assertEqual(
            set(response.data["sample_groups"][0].keys()),
            {"id", "name", "kind"},
        )

    def test_sample_write_sets_group_membership(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.sample.pk}),
            data=json.dumps({"sample_groups": [self.group.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(self.sample.sample_groups.all(), [self.group])

    def test_patch_groups_rolls_back_when_change_group_revoked_post_validation(
        self,
    ):
        """Revoking the group-edit capability after validation but before
        the write boundary must roll the whole PATCH back."""
        original_validate = SampleWriteSerializer.validate_sample_groups
        executed = []
        change_group = Permission.objects.get(
            codename="change_samplegroup",
            content_type__app_label="materials",
        )

        def revoke_after_validation(serializer, value):
            result = original_validate(serializer, value)
            executed.append(True)
            self.owner.user_permissions.remove(change_group)
            fresh = User.objects.get(pk=self.owner.pk)
            self.assertFalse(
                fresh.has_perm("materials.change_samplegroup"),
                "actor should have lost the related change capability",
            )
            self.assertTrue(
                fresh.has_perm("materials.change_sample"),
                "root write capability must remain",
            )
            self.assertTrue(fresh.is_active)
            return result

        self.owner.groups.clear()
        self.owner = User.objects.get(pk=self.owner.pk)
        revision_before = self.sample.content_revision
        self.assertTrue(self.owner.has_perm("materials.change_samplegroup"))
        self.client.force_login(self.owner)
        with patch.object(
            SampleWriteSerializer, "validate_sample_groups", revoke_after_validation
        ):
            response = self.client.patch(
                reverse("api-sample-detail", kwargs={"pk": self.sample.pk}),
                data=json.dumps(
                    {
                        "name": "Must roll back",
                        "sample_groups": [self.group.pk],
                    }
                ),
                content_type=JSON,
            )
        self.assertTrue(executed, "revoking validator did not run")
        self.sample.refresh_from_db()
        mutation = (
            f"name={self.sample.name!r} "
            f"revision={self.sample.content_revision} "
            f"groups={list(self.sample.sample_groups.all())!r}"
        )
        self.assertEqual(response.status_code, 400, mutation)
        self.assertEqual(self.sample.name, "Group API Sample", mutation)
        self.assertEqual(self.sample.content_revision, revision_before, mutation)
        self.assertNotIn(self.group, self.sample.sample_groups.all())
        self.assertFalse(ReviewAction.objects.filter(action="edited").exists())

    def test_post_groups_rolls_back_when_change_group_revoked_post_validation(
        self,
    ):
        """The same mid-flight revocation must abort a sample create: no
        row, no membership, no audit."""
        original_validate = SampleWriteSerializer.validate_sample_groups
        executed = []
        change_group = Permission.objects.get(
            codename="change_samplegroup",
            content_type__app_label="materials",
        )

        def revoke_after_validation(serializer, value):
            result = original_validate(serializer, value)
            executed.append(True)
            self.member.user_permissions.remove(change_group)
            fresh = User.objects.get(pk=self.member.pk)
            self.assertFalse(
                fresh.has_perm("materials.change_samplegroup"),
                "actor should have lost the related change capability",
            )
            self.assertTrue(
                fresh.has_perm("materials.add_sample"),
                "root create capability must remain",
            )
            self.assertTrue(fresh.is_active)
            return result

        self.member.groups.clear()
        self.member = User.objects.get(pk=self.member.pk)
        member_group = SampleGroup.objects.create(
            name="Member revoke group", kind="study", owner=self.member
        )
        self.assertTrue(self.member.has_perm("materials.add_sample"))
        self.assertTrue(self.member.has_perm("materials.change_samplegroup"))
        self.client.force_login(self.member)
        with patch.object(
            SampleWriteSerializer, "validate_sample_groups", revoke_after_validation
        ):
            response = self.client.post(
                reverse("api-sample-list"),
                data=json.dumps(
                    {
                        "name": "Revoked membership sample",
                        "material": self.material.pk,
                        "standalone": True,
                        "sample_groups": [member_group.pk],
                    }
                ),
                content_type=JSON,
            )
        self.assertTrue(executed, "revoking validator did not run")
        persisted = Sample.objects.filter(name="Revoked membership sample").first()
        mutation = (
            f"sample={persisted!r} "
            f"groups={list(persisted.sample_groups.all()) if persisted else []!r}"
        )
        self.assertEqual(response.status_code, 400, mutation)
        self.assertIsNone(persisted, mutation)
        self.assertFalse(ReviewAction.objects.exists())

    def test_sample_write_rejects_inaccessible_private_group(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.sample.pk}),
            data=json.dumps({"sample_groups": [self.foreign_private_group.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.sample.sample_groups.exists())

    def test_sample_write_rejects_visible_but_not_editable_group(self):
        self.client.force_login(self.owner)

        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.sample.pk}),
            data=json.dumps({"sample_groups": [self.foreign_published_group.pk]}),
            content_type=JSON,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.sample.sample_groups.exists())
