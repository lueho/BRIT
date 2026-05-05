from decimal import Decimal

from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from utils.properties.models import Unit
from utils.tests.testcases import ViewSetWithPermissionsTestCase

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
)
from ..serializers import (
    CompositionAPISerializer,
    MaterialAPISerializer,
    SampleAPISerializer,
    SampleSeriesAPISerializer,
)


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
        response = self.client.get(reverse("api-material-list"))
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertIn(self.private_material.name, names)

    def test_get_list_returns_all_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("api-material-list"))
        names = self._list_names(response)
        self.assertIn(self.published_material.name, names)
        self.assertIn(self.private_material.name, names)

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

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse("api-material-create"), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-material-update", kwargs={"pk": self.published_material.pk}
                ),
                data={},
            )

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-material-delete", kwargs={"pk": self.published_material.pk}
                ),
                data={},
            )


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
        """Return count of items in the list response."""
        return len(response.data)

    def test_get_list_http_200_ok_for_anonymous_user(self):
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_anonymous_excludes_private(self):
        # Anonymous user should only see published series
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)
        # Only one of the two series is published
        count = self._list_sample_counts(response)
        self.assertEqual(count, 1)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sampleseries-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_list_count_for_outsider_excludes_private(self):
        # Outsider (not owner) should only see published series
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-sampleseries-list"))
        count = self._list_sample_counts(response)
        self.assertEqual(count, 1)

    def test_get_list_count_for_owner_includes_private(self):
        # Owner should see both published and private series
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-sampleseries-list"))
        count = self._list_sample_counts(response)
        self.assertEqual(count, 2)

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

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse("api-sampleseries-create"), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-sampleseries-update", kwargs={"pk": self.published_series.pk}
                ),
                data={},
            )

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-sampleseries-delete", kwargs={"pk": self.published_series.pk}
                ),
                data={},
            )


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
        response = self.client.get(reverse("api-sample-list"))
        names = self._list_names(response)
        self.assertIn(self.published_sample.name, names)
        self.assertIn(self.private_sample.name, names)

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

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse("api-sample-create"), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse("api-sample-update", kwargs={"pk": self.published_sample.pk}),
                data={},
            )

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse("api-sample-delete", kwargs={"pk": self.published_sample.pk}),
                data={},
            )


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
        response = self.client.get(reverse("api-composition-list"))
        # Owner sees at least both the published and private compositions created in setUp.
        # The signal-created default composition may add extra rows.
        self.assertGreaterEqual(len(response.data), 2)

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

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse("api-composition-create"), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-composition-update",
                    kwargs={"pk": self.published_composition.pk},
                ),
                data={},
            )

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(
                reverse(
                    "api-composition-delete",
                    kwargs={"pk": self.published_composition.pk},
                ),
                data={},
            )
