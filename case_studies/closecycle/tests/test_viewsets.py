from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from maps.models import Region
from utils.object_management.models import User

from ..models import Showcase


class ShowcaseViewSetTestCase(TestCase):
    """Showcase API keeps public geo reads on UserCreatedObjectViewSet."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="owner")
        cls.outsider = User.objects.create(username="outsider")
        cls.region = Region.objects.create(
            name="Showcase Region", publication_status="published"
        )
        cls.published = Showcase.objects.create(
            name="Published Showcase",
            owner=cls.owner,
            region=cls.region,
            publication_status=Showcase.STATUS_PUBLISHED,
        )
        cls.private = Showcase.objects.create(
            name="Private Showcase",
            owner=cls.owner,
            region=cls.region,
            publication_status=Showcase.STATUS_PRIVATE,
        )

    def setUp(self):
        self.client = APIClient()

    def test_geojson_200_for_anonymous(self):
        response = self.client.get(reverse("api-showcase-geojson"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_version_200_for_anonymous(self):
        response = self.client.get(reverse("api-showcase-version"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_summaries_200_for_anonymous(self):
        response = self.client.get(reverse("api-showcase-summaries"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_excludes_private_showcases_for_anonymous(self):
        response = self.client.get(reverse("api-showcase-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.json()}
        self.assertIn(self.published.pk, ids)
        self.assertNotIn(self.private.pk, ids)

    def test_private_scope_includes_own_showcases(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-showcase-list"), {"scope": "private"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.json()}
        self.assertIn(self.published.pk, ids)
        self.assertIn(self.private.pk, ids)

    def test_retrieve_private_showcase_401_for_anonymous(self):
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_private_showcase_403_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_private_showcase_200_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_401_for_anonymous(self):
        response = self.client.post(
            reverse("api-showcase-list"), {"name": "New"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_403_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.patch(
            reverse("api-showcase-detail", args=[self.published.pk]),
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_options_list_200_for_anonymous(self):
        response = self.client.options(reverse("api-showcase-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_options_detail_200_for_anonymous(self):
        response = self.client.options(
            reverse("api-showcase-detail", args=[self.published.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _grant(self, user, codename):
        user.user_permissions.add(
            Permission.objects.get(
                codename=codename, content_type__app_label="closecycle"
            )
        )

    def test_update_403_for_owner_without_change_permission(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-showcase-detail", args=[self.private.pk]),
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.private.refresh_from_db()
        self.assertEqual(self.private.name, "Private Showcase")

    def test_update_200_for_owner_with_change_permission(self):
        self._grant(self.owner, "change_showcase")
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-showcase-detail", args=[self.private.pk]),
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private.refresh_from_db()
        self.assertEqual(self.private.name, "Renamed")

    def test_destroy_403_for_owner_without_delete_permission(self):
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-showcase-detail", args=[self.private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Showcase.objects.filter(pk=self.private.pk).exists())

    def test_destroy_204_for_owner_with_delete_permission(self):
        self._grant(self.owner, "delete_showcase")
        self.client.force_login(self.owner)
        response = self.client.delete(
            reverse("api-showcase-detail", args=[self.private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Showcase.objects.filter(pk=self.private.pk).exists())
