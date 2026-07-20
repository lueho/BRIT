from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.models import Collection

from ..models import UserCreatedObject


class BulkManageAccessViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pw")
        cls.editor = User.objects.create_user(username="editor", password="pw")
        cls.new_owner = User.objects.create_user(username="new_owner", password="pw")
        cls.other = User.objects.create_user(username="other", password="pw")
        cls.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        cls.collection_a = Collection.objects.create(
            name="Collection A",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.collection_b = Collection.objects.create(
            name="Collection B",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.foreign_collection = Collection.objects.create(
            name="Foreign Collection",
            owner=cls.other,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.content_type = ContentType.objects.get_for_model(Collection)
        cls.url = reverse("object_management:bulk_manage_access")

    def _item(self, obj):
        return f"{self.content_type.pk}:{obj.pk}"

    def test_bulk_add_editor_to_selected_objects(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [self._item(self.collection_a), self._item(self.collection_b)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection_a.editors.filter(pk=self.editor.pk).exists())
        self.assertTrue(self.collection_b.editors.filter(pk=self.editor.pk).exists())

    def test_bulk_remove_editor_from_selected_objects(self):
        self.collection_a.add_editor(self.editor)
        self.collection_b.add_editor(self.editor)
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "remove_editor",
                "username": self.editor.username,
                "items": [self._item(self.collection_a), self._item(self.collection_b)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.collection_a.editors.filter(pk=self.editor.pk).exists())
        self.assertFalse(self.collection_b.editors.filter(pk=self.editor.pk).exists())

    def test_bulk_transfer_ownership_of_selected_objects(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "transfer_ownership",
                "username": self.new_owner.username,
                "items": [self._item(self.collection_a), self._item(self.collection_b)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.collection_a.refresh_from_db()
        self.collection_b.refresh_from_db()
        self.assertEqual(self.collection_a.owner, self.new_owner)
        self.assertEqual(self.collection_b.owner, self.new_owner)

    def test_bulk_skips_objects_without_permission(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [
                    self._item(self.collection_a),
                    self._item(self.foreign_collection),
                ],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection_a.editors.filter(pk=self.editor.pk).exists())
        self.assertFalse(
            self.foreign_collection.editors.filter(pk=self.editor.pk).exists()
        )

    def test_staff_can_bulk_manage_foreign_objects(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [self._item(self.foreign_collection)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.foreign_collection.editors.filter(pk=self.editor.pk).exists()
        )

    def test_all_owned_add_editor(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "all_owned": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection_a.editors.filter(pk=self.editor.pk).exists())
        self.assertTrue(self.collection_b.editors.filter(pk=self.editor.pk).exists())
        self.assertFalse(
            self.foreign_collection.editors.filter(pk=self.editor.pk).exists()
        )

    def test_all_owned_transfer_ownership(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "transfer_ownership",
                "username": self.new_owner.username,
                "all_owned": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.collection_a.refresh_from_db()
        self.collection_b.refresh_from_db()
        self.foreign_collection.refresh_from_db()
        self.assertEqual(self.collection_a.owner, self.new_owner)
        self.assertEqual(self.collection_b.owner, self.new_owner)
        self.assertEqual(self.foreign_collection.owner, self.other)

    def test_unknown_username_fails_gracefully(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": "does-not-exist",
                "items": [self._item(self.collection_a)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.collection_a.editors.exists())

    def test_invalid_action_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "delete_everything",
                "username": self.editor.username,
                "items": [self._item(self.collection_a)],
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_malformed_items_are_ignored(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": ["not-an-item", "999999:1", self._item(self.collection_a)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection_a.editors.filter(pk=self.editor.pk).exists())

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [self._item(self.collection_a)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_private_list_shows_bulk_access_controls(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("collection-list-owned"), follow=True)
        self.assertContains(response, reverse("object_management:bulk_manage_access"))
        self.assertContains(
            response, f'value="{self.content_type.pk}:{self.collection_a.pk}"'
        )

    def test_published_list_hides_bulk_access_controls(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("collection-list"), follow=True)
        self.assertNotContains(
            response, reverse("object_management:bulk_manage_access")
        )

    def test_profile_page_shows_all_owned_access_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("user_profile"))
        self.assertContains(response, reverse("object_management:bulk_manage_access"))
        self.assertContains(response, 'name="all_owned"')

    def test_no_next_falls_back_to_private_list_of_model(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [self._item(self.collection_a)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{Collection.private_list_url()}?scope=private")

    def test_external_next_is_ignored(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "bulk_action": "add_editor",
                "username": self.editor.username,
                "items": [self._item(self.collection_a)],
                "next": "https://evil.example/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response.url)
