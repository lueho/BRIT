from types import SimpleNamespace

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.models import Collection

from ..models import ObjectEditorGrant, UserCreatedObject
from ..permissions import UserCreatedObjectPermission, get_object_policy


class OwnershipTransferModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.new_owner = User.objects.create_user(username="new_owner")
        cls.collection = Collection.objects.create(
            name="Test Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_transfer_ownership_changes_owner(self):
        self.collection.transfer_ownership(self.new_owner)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.owner, self.new_owner)

    def test_transfer_ownership_to_inactive_user_fails(self):
        self.new_owner.is_active = False
        self.new_owner.save()
        with self.assertRaises(ValidationError):
            self.collection.transfer_ownership(self.new_owner)

    def test_transfer_ownership_removes_editor_grant_of_new_owner(self):
        self.collection.add_editor(self.new_owner)
        self.collection.transfer_ownership(self.new_owner)
        self.assertFalse(self.collection.editors.filter(pk=self.new_owner.pk).exists())


class EditorGrantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.editor = User.objects.create_user(username="editor")
        cls.other = User.objects.create_user(username="other")
        cls.collection = Collection.objects.create(
            name="Test Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_add_and_remove_editor(self):
        self.collection.add_editor(self.editor, granted_by=self.owner)
        self.assertTrue(self.collection.editors.filter(pk=self.editor.pk).exists())
        self.assertTrue(self.collection.is_editable_by(self.editor))

        self.collection.remove_editor(self.editor)
        self.assertFalse(self.collection.editors.filter(pk=self.editor.pk).exists())
        self.assertFalse(self.collection.is_editable_by(self.editor))

    def test_add_editor_is_idempotent(self):
        self.collection.add_editor(self.editor)
        self.collection.add_editor(self.editor)
        self.assertEqual(
            ObjectEditorGrant.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
            ).count(),
            1,
        )

    def test_cannot_add_owner_as_editor(self):
        with self.assertRaises(ValidationError):
            self.collection.add_editor(self.owner)

    def test_owner_is_editable_by(self):
        self.assertTrue(self.collection.is_editable_by(self.owner))
        self.assertFalse(self.collection.is_editable_by(self.other))

    def test_accessible_by_user_includes_shared_objects(self):
        self.collection.add_editor(self.editor)
        self.assertIn(
            self.collection, Collection.objects.accessible_by_user(self.editor)
        )
        self.assertNotIn(
            self.collection, Collection.objects.accessible_by_user(self.other)
        )

    def test_editable_by_user_queryset(self):
        self.collection.add_editor(self.editor)
        self.assertIn(self.collection, Collection.objects.editable_by_user(self.editor))
        self.assertIn(self.collection, Collection.objects.editable_by_user(self.owner))
        self.assertNotIn(
            self.collection, Collection.objects.editable_by_user(self.other)
        )


class EditorPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.editor = User.objects.create_user(username="editor")
        cls.other = User.objects.create_user(username="other")
        cls.staff = User.objects.create_user(username="staff", is_staff=True)
        cls.collection = Collection.objects.create(
            name="Test Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def setUp(self):
        self.collection.add_editor(self.editor)
        self.permission = UserCreatedObjectPermission()

    def _request(self, user, method="PATCH", data=None):
        return SimpleNamespace(user=user, method=method, data=data or {})

    def test_editor_can_read_private_object(self):
        request = self._request(self.editor, method="GET")
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_other_cannot_read_private_object(self):
        request = self._request(self.other, method="GET")
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_can_modify_non_status_fields(self):
        request = self._request(self.editor, data={"name": "Renamed"})
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_cannot_change_publication_status(self):
        request = self._request(
            self.editor, data={"publication_status": UserCreatedObject.STATUS_PUBLISHED}
        )
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_cannot_modify_published_object(self):
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.collection.save()
        request = self._request(self.editor, data={"name": "Renamed"})
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_cannot_delete(self):
        request = self._request(self.editor, method="DELETE")
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_who_is_moderator_keeps_moderator_rights(self):
        from django.contrib.auth.models import Permission

        moderate_perm = Permission.objects.get(
            codename="can_moderate_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )
        self.editor.user_permissions.add(moderate_perm)
        moderator_editor = User.objects.get(pk=self.editor.pk)  # reset perm cache
        self.collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.collection.save()
        request = self._request(
            moderator_editor,
            data={"publication_status": UserCreatedObject.STATUS_PUBLISHED},
        )
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_who_is_moderator_can_edit_private_content(self):
        from django.contrib.auth.models import Permission

        moderate_perm = Permission.objects.get(
            codename="can_moderate_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )
        self.editor.user_permissions.add(moderate_perm)
        moderator_editor = User.objects.get(pk=self.editor.pk)  # reset perm cache
        request = self._request(moderator_editor, data={"description": "updated"})
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_cannot_change_owner(self):
        request = self._request(self.editor, data={"owner": self.editor.pk})
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.collection)
        )

    def test_editor_grants_deleted_with_object(self):
        grant_qs = ObjectEditorGrant.for_object(self.collection)
        self.assertTrue(grant_qs.filter(editor=self.editor).exists())
        content_type = ContentType.objects.get_for_model(Collection)
        object_id = self.collection.pk
        self.collection.delete()
        self.assertFalse(
            ObjectEditorGrant.objects.filter(
                content_type=content_type, object_id=object_id
            ).exists()
        )

    def test_is_editor_check_is_cached_per_user(self):
        other_collection = Collection.objects.create(
            name="Second Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        ContentType.objects.get_for_model(Collection)  # warm ContentType cache
        self.assertTrue(self.permission._is_editor(self.editor, self.collection))
        with self.assertNumQueries(0):
            self.assertTrue(self.permission._is_editor(self.editor, self.collection))
            self.assertFalse(self.permission._is_editor(self.editor, other_collection))

    def test_transfer_ownership_permission(self):
        for user, expected in [
            (self.owner, True),
            (self.staff, True),
            (self.editor, False),
            (self.other, False),
        ]:
            request = self._request(user, method="POST")
            self.assertEqual(
                self.permission.has_transfer_ownership_permission(
                    request, self.collection
                ),
                expected,
            )

    def test_manage_editors_permission(self):
        for user, expected in [
            (self.owner, True),
            (self.staff, True),
            (self.editor, False),
            (self.other, False),
        ]:
            request = self._request(user, method="POST")
            self.assertEqual(
                self.permission.has_manage_editors_permission(request, self.collection),
                expected,
            )


class EditorObjectPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.editor = User.objects.create_user(username="editor")
        cls.other = User.objects.create_user(username="other")
        cls.staff = User.objects.create_user(username="staff", is_staff=True)
        cls.collection = Collection.objects.create(
            name="Test Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def setUp(self):
        self.collection.add_editor(self.editor)

    def test_policy_flags_for_editor(self):
        policy = get_object_policy(self.editor, self.collection)
        self.assertTrue(policy["is_editor"])
        self.assertFalse(policy["can_transfer_ownership"])
        self.assertFalse(policy["can_manage_editors"])

    def test_policy_flags_for_owner(self):
        policy = get_object_policy(self.owner, self.collection)
        self.assertFalse(policy["is_editor"])
        self.assertTrue(policy["can_transfer_ownership"])
        self.assertTrue(policy["can_manage_editors"])

    def test_policy_flags_for_staff(self):
        policy = get_object_policy(self.staff, self.collection)
        self.assertTrue(policy["can_transfer_ownership"])
        self.assertTrue(policy["can_manage_editors"])

    def test_policy_flags_for_other(self):
        policy = get_object_policy(self.other, self.collection)
        self.assertFalse(policy["is_editor"])
        self.assertFalse(policy["can_transfer_ownership"])
        self.assertFalse(policy["can_manage_editors"])

    def test_editor_with_change_permission_can_edit(self):
        from django.contrib.auth.models import Permission

        change_perm = Permission.objects.get(
            codename="change_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )
        self.editor.user_permissions.add(change_perm)
        editor = User.objects.get(pk=self.editor.pk)  # reset perm cache
        policy = get_object_policy(editor, self.collection)
        self.assertTrue(policy["can_edit"])


class OwnershipSharingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pw")
        cls.new_owner = User.objects.create_user(username="new_owner", password="pw")
        cls.editor = User.objects.create_user(username="editor", password="pw")
        cls.other = User.objects.create_user(username="other", password="pw")
        cls.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        cls.collection = Collection.objects.create(
            name="Test Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.content_type = ContentType.objects.get_for_model(Collection)

    def _url(self, name):
        return reverse(
            f"object_management:{name}",
            kwargs={
                "content_type_id": self.content_type.pk,
                "object_id": self.collection.pk,
            },
        )

    def test_owner_can_transfer_ownership(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("transfer_ownership"), {"new_owner": self.new_owner.username}
        )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.owner, self.new_owner)

    def test_staff_can_transfer_ownership(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self._url("transfer_ownership"), {"new_owner": self.new_owner.username}
        )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.owner, self.new_owner)

    def test_non_owner_cannot_transfer_ownership(self):
        self.client.force_login(self.other)
        response = self.client.post(
            self._url("transfer_ownership"), {"new_owner": self.other.username}
        )
        self.assertEqual(response.status_code, 403)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.owner, self.owner)

    def test_transfer_to_unknown_user_fails_gracefully(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("transfer_ownership"), {"new_owner": "does-not-exist"}
        )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.owner, self.owner)

    def test_owner_can_add_editor(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("add_editor"), {"user": self.editor.username}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection.editors.filter(pk=self.editor.pk).exists())

    def test_owner_can_remove_editor(self):
        self.collection.add_editor(self.editor)
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("remove_editor"), {"user": self.editor.username}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.collection.editors.filter(pk=self.editor.pk).exists())

    def test_non_owner_cannot_add_editor(self):
        self.client.force_login(self.other)
        response = self.client.post(
            self._url("add_editor"), {"user": self.other.username}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.collection.editors.filter(pk=self.other.pk).exists())

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.post(
            self._url("transfer_ownership"), {"new_owner": self.new_owner.username}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_manage_access_modal_renders_for_owner(self):
        self.collection.add_editor(self.editor)
        self.client.force_login(self.owner)
        response = self.client.get(self._url("manage_access_modal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "editor")

    def test_manage_access_modal_forbidden_for_other(self):
        self.client.force_login(self.other)
        response = self.client.get(self._url("manage_access_modal"))
        self.assertEqual(response.status_code, 403)

    def test_filter_queryset_for_user_includes_editor_grants(self):
        from utils.object_management.permissions import filter_queryset_for_user

        self.collection.add_editor(self.editor)
        queryset = filter_queryset_for_user(Collection.objects.all(), self.editor)
        self.assertIn(self.collection, queryset)
        other_queryset = filter_queryset_for_user(Collection.objects.all(), self.other)
        self.assertNotIn(self.collection, other_queryset)

    def test_editor_can_view_private_detail_page(self):
        self.collection.add_editor(self.editor)
        self.client.force_login(self.editor)
        response = self.client.get(self.collection.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_other_cannot_view_private_detail_page(self):
        self.client.force_login(self.other)
        response = self.client.get(self.collection.get_absolute_url())
        self.assertEqual(response.status_code, 403)

    def test_external_next_url_is_ignored(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("add_editor"),
            {"user": self.editor.username, "next": "https://evil.example/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response.url)
