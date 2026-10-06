from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from processes.models import Process

from ..models import ObjectGroupEditorGrant
from ..permissions import get_object_policy


class GroupAccessManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="access-owner")
        cls.member = User.objects.create_user(username="access-member")
        cls.other = User.objects.create_user(username="access-other")
        cls.staff = User.objects.create_user(username="access-staff", is_staff=True)
        cls.group = Group.objects.create(name="Workshop editors")
        cls.group.permissions.add(
            Permission.objects.get(
                content_type__app_label="processes", codename="change_process"
            )
        )
        cls.member.groups.add(cls.group)
        cls.process = Process.objects.create(name="Managed process", owner=cls.owner)
        cls.unshared = Process.objects.create(
            name="Other managed process", owner=cls.owner
        )
        cls.content_type = ContentType.objects.get_for_model(Process)

    def setUp(self):
        self.client.force_login(self.owner)

    def url(self, action, process=None):
        return reverse(
            f"object_management:{action}",
            kwargs={
                "content_type_id": self.content_type.pk,
                "object_id": (process or self.process).pk,
            },
        )

    def grant(self, process=None, group=None):
        return ObjectGroupEditorGrant.objects.create(
            content_type=self.content_type,
            object_id=(process or self.process).pk,
            group=group or self.group,
            granted_by=self.staff,
        )

    def test_model_group_grant_helpers_are_idempotent(self):
        first = self.process.add_editor_group(self.group, granted_by=self.owner)
        second = self.process.add_editor_group(self.group, granted_by=self.staff)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.granted_by, self.owner)
        self.assertIn(self.group, self.process.editor_groups)
        self.assertEqual(self.process.group_editor_grants.count(), 1)
        self.process.remove_editor_group(self.group)
        self.assertFalse(self.process.group_editor_grants.exists())

    def test_owner_can_grant_group_access(self):
        response = self.client.post(
            self.url("add_editor_group"), {"group": self.group.name}
        )
        self.assertEqual(response.status_code, 302)
        grant = ObjectGroupEditorGrant.for_object(self.process).get(group=self.group)
        self.assertEqual(grant.granted_by, self.owner)
        self.assertTrue(get_object_policy(self.member, self.process)["can_edit"])
        self.assertFalse(get_object_policy(self.member, self.unshared)["can_edit"])

    def test_staff_can_grant_group_access(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url("add_editor_group"), {"group": self.group.name}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ObjectGroupEditorGrant.for_object(self.process).get().granted_by, self.staff
        )

    def test_group_grants_do_not_change_membership_or_model_permissions(self):
        members = set(self.group.user_set.values_list("pk", flat=True))
        permissions = set(self.group.permissions.values_list("pk", flat=True))
        self.client.post(self.url("add_editor_group"), {"group": self.group.name})
        self.assertEqual(set(self.group.user_set.values_list("pk", flat=True)), members)
        self.assertEqual(
            set(self.group.permissions.values_list("pk", flat=True)), permissions
        )

    def test_repeated_add_does_not_duplicate_grant_or_replace_actor(self):
        self.client.post(self.url("add_editor_group"), {"group": self.group.name})
        self.client.force_login(self.staff)
        self.client.post(self.url("add_editor_group"), {"group": self.group.name})
        grants = ObjectGroupEditorGrant.for_object(self.process)
        self.assertEqual(grants.count(), 1)
        self.assertEqual(grants.get().granted_by, self.owner)

    def test_group_name_is_trimmed(self):
        response = self.client.post(
            self.url("add_editor_group"), {"group": f"  {self.group.name}  "}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ObjectGroupEditorGrant.for_object(self.process).exists())

    def test_unknown_group_is_reported_without_creating_group_or_grant(self):
        before = Group.objects.count()
        response = self.client.post(
            self.url("add_editor_group"), {"group": "Unknown group"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "does not exist",
            " ".join(str(message) for message in get_messages(response.wsgi_request)),
        )
        self.assertEqual(Group.objects.count(), before)
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())

    def test_owner_can_revoke_operator_created_group_grant_on_one_object(self):
        self.grant()
        other_grant = self.grant(process=self.unshared)
        response = self.client.post(
            self.url("remove_editor_group"), {"group": self.group.name}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())
        self.assertTrue(
            ObjectGroupEditorGrant.objects.filter(pk=other_grant.pk).exists()
        )
        self.assertFalse(get_object_policy(self.member, self.process)["can_edit"])
        self.assertTrue(self.group.user_set.filter(pk=self.member.pk).exists())

    def test_staff_can_revoke_group_access(self):
        self.grant()
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(
                self.url("remove_editor_group"), {"group": self.group.name}
            ).status_code,
            302,
        )
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())

    def test_removing_group_grant_preserves_individual_access(self):
        self.grant()
        self.process.add_editor(self.member)
        self.client.post(self.url("remove_editor_group"), {"group": self.group.name})
        self.assertTrue(get_object_policy(self.member, self.process)["can_edit"])
        self.assertTrue(self.process.editor_grants.filter(editor=self.member).exists())

    def test_removing_individual_grant_reports_only_direct_revocation(self):
        self.grant()
        self.process.add_editor(self.member)
        response = self.client.post(
            self.url("remove_editor"), {"user": self.member.username}
        )
        message = " ".join(str(item) for item in get_messages(response.wsgi_request))
        self.assertIn("direct edit grant", message)
        self.assertNotIn("can no longer edit", message)
        self.assertTrue(get_object_policy(self.member, self.process)["can_edit"])

    def test_owner_dialog_displays_direct_users_and_granted_groups(self):
        self.grant()
        self.process.add_editor(self.member)
        response = self.client.get(self.url("manage_access_modal"))
        self.assertContains(response, self.member.username)
        self.assertContains(response, self.group.name)
        self.assertContains(response, "Direct user grants")
        self.assertContains(response, "Group grants")
        self.assertContains(response, self.url("add_editor_group"))
        self.assertContains(response, self.url("remove_editor_group"))
        self.assertContains(response, "change permission")
        self.assertNotContains(response, "No other users have edit access.")

    def test_group_only_dialog_does_not_claim_nobody_has_access(self):
        self.grant()
        response = self.client.get(self.url("manage_access_modal"))
        self.assertContains(response, self.group.name)
        self.assertContains(response, "No direct user grants.")
        self.assertNotContains(response, "No other users have edit access.")

    def test_group_names_are_html_escaped(self):
        self.group.name = "<script>group</script>"
        self.group.save()
        self.grant()
        response = self.client.get(self.url("manage_access_modal"))
        self.assertContains(response, "&lt;script&gt;group&lt;/script&gt;")
        self.assertNotContains(response, "<script>group</script>")

    def test_non_owner_editors_and_moderators_cannot_manage_group_grants(self):
        self.grant()
        self.process.add_editor(self.other)
        self.other.user_permissions.add(
            Permission.objects.get(
                content_type=self.content_type, codename="can_moderate_process"
            )
        )
        for user in (self.member, self.other):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(self.url("manage_access_modal")).status_code, 403
            )
            for action in ("add_editor_group", "remove_editor_group"):
                with self.subTest(user=user.username, action=action):
                    response = self.client.post(
                        self.url(action), {"group": self.group.name}
                    )
                    self.assertEqual(response.status_code, 403)
        self.assertEqual(ObjectGroupEditorGrant.for_object(self.process).count(), 1)

    def test_anonymous_group_management_requires_login(self):
        self.client.logout()
        for action in ("add_editor_group", "remove_editor_group"):
            response = self.client.post(self.url(action), {"group": self.group.name})
            self.assertEqual(response.status_code, 302)
            self.assertIn("login", response.url)
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())

    @override_settings(
        MIDDLEWARE=[*settings.MIDDLEWARE, "django.middleware.csrf.CsrfViewMiddleware"]
    )
    def test_group_management_is_post_only_and_csrf_protected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        for action in ("add_editor_group", "remove_editor_group"):
            self.assertEqual(self.client.get(self.url(action)).status_code, 405)
            self.assertEqual(
                csrf_client.post(
                    self.url(action), {"group": self.group.name}
                ).status_code,
                403,
            )
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())

    def test_group_actions_reject_non_user_created_objects(self):
        url = reverse(
            "object_management:add_editor_group",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Group).pk,
                "object_id": self.group.pk,
            },
        )
        self.assertEqual(
            self.client.post(url, {"group": self.group.name}).status_code, 404
        )

    def test_group_action_redirects_reject_external_next(self):
        response = self.client.post(
            self.url("add_editor_group"),
            {
                "group": self.group.name,
                "next": "https://example.org/redirect",
            },
        )
        self.assertEqual(response.url, self.process.get_absolute_url())

    def test_modal_dispatches_group_and_individual_actions(self):
        for action, data in (
            ("add_editor_group", {"group": self.group.name}),
            ("add_editor", {"user": self.member.username}),
        ):
            response = self.client.post(
                self.url("manage_access_modal"), {"access_action": action, **data}
            )
            self.assertEqual(response.status_code, 302)
        self.assertTrue(ObjectGroupEditorGrant.for_object(self.process).exists())
        self.assertTrue(self.process.editor_grants.exists())
        for action, data in (
            ("remove_editor_group", {"group": self.group.name}),
            ("remove_editor", {"user": self.member.username}),
        ):
            response = self.client.post(
                self.url("manage_access_modal"), {"access_action": action, **data}
            )
            self.assertEqual(response.status_code, 302)
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())
        self.assertFalse(self.process.editor_grants.exists())

    def test_modal_group_ajax_preflight_does_not_mutate_access(self):
        response = self.client.post(
            self.url("manage_access_modal"),
            {
                "access_action": "add_editor_group",
                "group": self.group.name,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())

    def test_future_group_members_inherit_access(self):
        self.client.post(self.url("add_editor_group"), {"group": self.group.name})
        self.other.groups.add(self.group)
        self.assertTrue(get_object_policy(self.other, self.process)["can_edit"])

    def test_grant_without_change_permission_allows_reading_but_not_editing(self):
        self.group.permissions.clear()
        self.client.post(self.url("add_editor_group"), {"group": self.group.name})
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.process.get_absolute_url()).status_code, 200
        )
        member = User.objects.get(pk=self.member.pk)
        self.assertFalse(get_object_policy(member, self.process)["can_edit"])
        self.assertEqual(self.group.permissions.count(), 0)

    def test_revoking_one_group_preserves_another_group_grant(self):
        self.grant()
        other_group = Group.objects.create(name="Other editors")
        self.member.groups.add(other_group)
        self.grant(group=other_group)
        self.client.post(self.url("remove_editor_group"), {"group": self.group.name})
        self.assertTrue(get_object_policy(self.member, self.process)["can_edit"])
        self.assertEqual(
            ObjectGroupEditorGrant.for_object(self.process).get().group, other_group
        )

    def test_new_owner_can_inspect_and_revoke_existing_group_grants(self):
        self.grant()
        self.process.transfer_ownership(self.other)
        self.client.force_login(self.other)
        self.assertContains(
            self.client.get(self.url("manage_access_modal")), self.group.name
        )
        self.assertEqual(
            self.client.post(
                self.url("remove_editor_group"), {"group": self.group.name}
            ).status_code,
            302,
        )
        self.assertFalse(ObjectGroupEditorGrant.for_object(self.process).exists())
