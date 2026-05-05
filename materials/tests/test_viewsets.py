import json
from decimal import Decimal

from django.urls import reverse

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
    SampleSeries,
)
from ..serializers import (
    CompositionAPISerializer,
    MaterialAPISerializer,
    SampleAPISerializer,
    SampleSeriesAPISerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JSON = "application/json"


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

    def test_get_list_returns_all_for_staff(self):
        self.client.force_login(self.staff)
        # Unrecognised scope falls back to filter_queryset_for_user, which returns
        # the full queryset for staff users.
        response = self.client.get(reverse("api-material-list") + "?scope=all")
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertIn(self.private_material.name, names)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_401_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertIn(response.status_code, (401, 403))

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 403)

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

    def test_patch_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

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

    def test_patch_http_403_for_owner_on_published(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-material-detail", kwargs={"pk": self.published_material.pk}),
            data=json.dumps({"name": "Should Not Work"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

    # --- delete ---

    def test_delete_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.delete(
            reverse("api-material-detail", kwargs={"pk": self.private_material.pk})
        )
        self.assertEqual(response.status_code, 403)

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

    def test_get_detail_http_401_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk})
        )
        self.assertIn(response.status_code, (401, 403))

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.published_series.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk})
        )
        self.assertEqual(response.status_code, 403)

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

    def test_patch_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-sampleseries-detail", kwargs={"pk": self.private_series.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

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

    def test_delete_http_204_for_owner_on_private(self):
        to_delete = SampleSeries.objects.create(
            name="To Delete Series",
            material=self.material,
            owner=self.owner,
            publication_status="private",
        )
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

    def test_get_detail_http_401_for_anonymous_on_private(self):
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk})
        )
        self.assertIn(response.status_code, (401, 403))

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.published_sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk})
        )
        self.assertEqual(response.status_code, 403)

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
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            Sample.objects.filter(name="Member Sample", owner=self.member).exists()
        )

    # --- update ---

    def test_patch_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-sample-detail", kwargs={"pk": self.private_sample.pk}),
            data=json.dumps({"name": "Hacked"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

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


class CompositionViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = (
        "view_composition",
        "add_composition",
        "change_composition",
        "delete_composition",
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
        cls.group = MaterialComponentGroup.objects.create(name="Test Component Group")
        cls.published_composition = Composition.objects.create(
            name="Published Composition",
            sample=cls.sample,
            group=cls.group,
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_composition = Composition.objects.create(
            name="Private Composition",
            sample=cls.sample,
            group=cls.group,
            owner=cls.owner,
            publication_status="private",
        )

    # --- list visibility ---

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_anonymous_excludes_private(self):
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_outsider_excludes_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-composition-list"))
        self.assertEqual(len(response.data), 1)

    def test_get_list_count_for_owner_includes_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-composition-list") + "?scope=private")
        # Owner sees at least both the published and private compositions created in
        # setUp. The signal-created default composition may add extra rows.
        self.assertGreaterEqual(len(response.data), 2)

    # --- detail visibility ---

    def test_get_detail_http_200_ok_for_anonymous_on_published(self):
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.published_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_401_for_anonymous_on_private(self):
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.private_composition.pk}
            )
        )
        self.assertIn(response.status_code, (401, 403))

    def test_get_detail_http_200_ok_for_outsider_on_published(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.published_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-composition-detail", kwargs={"pk": self.private_composition.pk}
            )
        )
        self.assertEqual(response.status_code, 403)

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

    def test_post_http_201_for_member_with_add_permission(self):
        extra_group = MaterialComponentGroup.objects.create(
            name="Extra Group For Composition"
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-composition-list"),
            data=json.dumps({"sample": self.sample.pk, "group": extra_group.pk}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Composition.objects.filter(
                sample=self.sample, group=extra_group, owner=self.member
            ).exists()
        )

    # --- update ---

    def test_patch_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse(
                "api-composition-detail",
                kwargs={"pk": self.private_composition.pk},
            ),
            data=json.dumps({"order": 50}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

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
        cls.group = MaterialComponentGroup.objects.create(name="CM Test Group")
        cls.component = MaterialComponent.objects.create(name="CM Test Component")
        cls.unit = Unit.objects.create(name="CM Test Unit", symbol="cmu")
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

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

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

    def test_post_http_201_for_member_with_add_permission(self):
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
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ComponentMeasurement.objects.filter(
                sample=self.sample,
                component=self.component,
                average=Decimal("5.0"),
                owner=self.member,
            ).exists()
        )

    # --- update ---

    def test_patch_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse(
                "api-componentmeasurement-detail",
                kwargs={"pk": self.private_measurement.pk},
            ),
            data=json.dumps({"average": "99.0"}),
            content_type=JSON,
        )
        self.assertEqual(response.status_code, 403)

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
        cls.prop = MaterialProperty.objects.create(
            name="MPV Test Property", owner=cls.owner
        )
        cls.unit = Unit.objects.create(name="MPV Test Unit", symbol="mpvu")
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

    def test_get_detail_http_403_for_outsider_on_private(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(
                "api-materialpropertyvalue-detail",
                kwargs={"pk": self.private_value.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

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

    def test_post_http_201_for_member_with_add_permission(self):
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
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            MaterialPropertyValue.objects.filter(
                sample=self.sample,
                property=self.prop,
                average=Decimal("50.0"),
                owner=self.member,
            ).exists()
        )

    # --- update ---

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
