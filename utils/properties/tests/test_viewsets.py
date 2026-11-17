from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from utils.properties.models import Property, Unit


class PropertyReferenceViewSetPolicyTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="reference-owner")
        cls.stranger = User.objects.create_user(username="reference-stranger")
        cls.private_unit = Unit.objects.create(
            name="Private Reference Unit",
            owner=cls.owner,
            publication_status="private",
        )
        cls.private_property = Property.objects.create(
            name="Private Reference Property",
            owner=cls.owner,
            publication_status="private",
        )

    def test_unit_routes_only_expose_private_unit_to_its_owner(self):
        self.client.force_login(self.stranger)
        list_response = self.client.get(reverse("api-unit-list"))
        detail_response = self.client.get(
            reverse("api-unit-detail", args=[self.private_unit.pk])
        )
        self.assertNotIn(
            self.private_unit.name,
            [item["name"] for item in list_response.data],
        )
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.owner)
        owner_list = self.client.get(reverse("api-unit-list"))
        owner_detail = self.client.get(
            reverse("api-unit-detail", args=[self.private_unit.pk])
        )
        self.assertIn(
            self.private_unit.name,
            [item["name"] for item in owner_list.data],
        )
        self.assertEqual(owner_detail.status_code, status.HTTP_200_OK)

    def test_property_routes_only_expose_private_property_to_its_owner(self):
        self.client.force_login(self.stranger)
        list_response = self.client.get(reverse("api-property-list"))
        detail_response = self.client.get(
            reverse("api-property-detail", args=[self.private_property.pk])
        )
        self.assertNotIn(
            self.private_property.name,
            [item["name"] for item in list_response.data],
        )
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.owner)
        owner_list = self.client.get(reverse("api-property-list"))
        owner_detail = self.client.get(
            reverse("api-property-detail", args=[self.private_property.pk])
        )
        self.assertIn(
            self.private_property.name,
            [item["name"] for item in owner_list.data],
        )
        self.assertEqual(owner_detail.status_code, status.HTTP_200_OK)
