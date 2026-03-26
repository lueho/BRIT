from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from utils.object_management.models import User
from utils.tests.testcases import ViewSetWithPermissionsTestCase

from ..models import Author, Source


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


class SourceCreateAPIViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.member = User.objects.create(username="member")
        self.outsider = User.objects.create(username="outsider")
        self.member.user_permissions.add(
            Permission.objects.get(
                codename="add_source",
                content_type__app_label="bibliography",
            )
        )

    def test_create_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("api-source-create"),
            {"title": "Inline source"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_201_created_for_member_sets_owner_and_fields(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-source-create"),
            {
                "title": "Inline source",
                "type": "book",
                "publisher": "Test Publisher",
                "year": 2024,
                "attributions": "Stand: 16.11.2023",
                "url": "https://example.com/source.pdf",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        source = Source.objects.get(pk=payload["id"])

        self.assertEqual(source.owner, self.member)
        self.assertEqual(source.title, "Inline source")
        self.assertEqual(source.type, "book")
        self.assertEqual(source.publisher, "Test Publisher")
        self.assertEqual(source.year, 2024)
        self.assertEqual(source.attributions, "Stand: 16.11.2023")
        self.assertEqual(source.url, "https://example.com/source.pdf")
        self.assertEqual(payload["publication_status"], Source.STATUS_PRIVATE)

    def test_create_201_created_for_member_with_existing_author(self):
        self.client.force_login(self.member)
        author = Author.objects.create(
            owner=self.member,
            first_names="Ada",
            last_names="Lovelace",
        )

        response = self.client.post(
            reverse("api-source-create"),
            {
                "title": "Inline source",
                "authors": [{"id": author.pk}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = Source.objects.get(pk=response.json()["id"])
        self.assertEqual(source.sourceauthors.count(), 1)
        source_author = source.sourceauthors.get()
        self.assertEqual(source_author.author_id, author.pk)
        self.assertEqual(source_author.position, 1)

    def test_create_403_when_new_author_payload_without_add_author_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-source-create"),
            {
                "title": "Inline source",
                "authors": [{"first_names": "Ada", "last_names": "Lovelace"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_201_creates_source_and_new_author_when_permitted(self):
        self.member.user_permissions.add(
            Permission.objects.get(
                codename="add_author",
                content_type__app_label="bibliography",
            )
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("api-source-create"),
            {
                "title": "Inline source",
                "authors": [{"first_names": "Ada", "last_names": "Lovelace"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = Source.objects.get(pk=response.json()["id"])
        self.assertEqual(source.owner, self.member)
        self.assertEqual(source.sourceauthors.count(), 1)
        self.assertEqual(source.sourceauthors.get().author.owner, self.member)

    def test_generic_source_viewset_create_is_not_allowed(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("api-source-list"),
            {"title": "Unsafe path"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
