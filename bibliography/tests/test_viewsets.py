from django.urls import reverse
from rest_framework import status

from utils.tests.testcases import ViewSetWithPermissionsTestCase

from ..models import Author


class AuthorViewSetPermissionTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ["view_author", "add_author", "change_author", "delete_author"]

    def setUp(self):
        self.author_data = {
            "first_names": "John",
            "middle_names": "F.",
            "last_names": "Kennedy",
            "suffix": "Jr.",
            "preferred_citation": "J.F.K. Jr.",
        }
        self.author = Author.objects.create(**self.author_data)

    def test_list_200_ok_for_anonymous(self):
        response = self.client.get(reverse("api-author-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("api-author-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("api-author-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_401_unauthorized_for_anonymous(self):
        response = self.client.post(
            reverse("api-author-list"), self.author_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("api-author-list"), self.author_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_201_created_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-author-list"), self.author_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_200_ok_for_anonymous(self):
        response = self.client.get(
            reverse("api-author-detail", args=[self.author.id]), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_200_ok_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("api-author-detail", args=[self.author.id]), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("api-author-detail", args=[self.author.id]), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_401_unauthorized_for_anonymous(self):
        response = self.client.put(
            reverse("api-author-detail", args=[self.author.id]),
            self.author_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.put(
            reverse("api-author-detail", args=[self.author.id]),
            self.author_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.put(
            reverse("api-author-detail", args=[self.author.id]),
            self.author_data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_401_unauthorized_for_anonymous(self):
        response = self.client.delete(
            reverse("api-author-detail", args=[self.author.id])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.delete(
            reverse("api-author-detail", args=[self.author.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_204_no_content_for_member(self):
        self.client.force_login(self.member)
        response = self.client.delete(
            reverse("api-author-detail", args=[self.author.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
