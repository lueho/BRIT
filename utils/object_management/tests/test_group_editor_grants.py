from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from materials.models import Material
from processes.models import Process, ProcessCategory

from ..models import ObjectGroupEditorGrant
from ..permissions import (
    UserCreatedObjectPermission,
    apply_scope_filter,
    filter_queryset_for_user,
    get_object_policy,
)


class GroupEditorGrantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="group-grant-owner")
        cls.member = User.objects.create_user(username="group-grant-member")
        cls.other = User.objects.create_user(username="group-grant-other")
        cls.group = Group.objects.create(name="group-grant-workshop")
        cls.group.permissions.add(
            Permission.objects.get(
                content_type__app_label="processes", codename="change_process"
            )
        )
        cls.member.groups.add(cls.group)
        cls.process = Process.objects.create(name="Shared process", owner=cls.owner)
        cls.unshared = Process.objects.create(name="Unshared process", owner=cls.owner)
        cls.grant = ObjectGroupEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Process),
            object_id=cls.process.pk,
            group=cls.group,
            granted_by=cls.owner,
        )

    def test_model_and_queryset_access_include_only_assigned_objects(self):
        self.assertTrue(self.process.is_editable_by(self.member))
        self.assertFalse(self.unshared.is_editable_by(self.member))
        self.assertFalse(self.process.is_editable_by(self.other))
        for queryset in (
            Process.objects.editable_by_user(self.member),
            Process.objects.accessible_by_user(self.member),
            filter_queryset_for_user(Process.objects.all(), self.member),
            apply_scope_filter(Process.objects.all(), "private", self.member),
        ):
            self.assertIn(self.process, queryset)
            self.assertNotIn(self.unshared, queryset)

    def test_anonymous_users_have_no_shared_access(self):
        user = AnonymousUser()
        self.assertFalse(self.process.is_editable_by(user))
        self.assertNotIn(
            self.process, filter_queryset_for_user(Process.objects.all(), user)
        )
        self.assertFalse(UserCreatedObjectPermission().is_editor(user, self.process))

    def test_removing_membership_revokes_shared_access(self):
        self.member.groups.remove(self.group)
        member = User.objects.get(pk=self.member.pk)
        self.assertFalse(self.process.is_editable_by(member))
        self.assertFalse(get_object_policy(member, self.process)["can_edit"])
        self.assertNotIn(
            self.process, filter_queryset_for_user(Process.objects.all(), member)
        )

    def test_new_members_inherit_access_without_new_grants(self):
        self.other.groups.add(self.group)
        self.assertTrue(get_object_policy(self.other, self.process)["can_edit"])
        self.assertEqual(ObjectGroupEditorGrant.objects.count(), 1)

    def test_removing_group_grant_preserves_individual_grant(self):
        self.process.add_editor(self.member)
        self.grant.delete()
        self.assertTrue(self.process.is_editable_by(self.member))
        self.assertTrue(get_object_policy(self.member, self.process)["can_edit"])

    def test_overlapping_grants_do_not_duplicate_queryset_rows(self):
        self.process.add_editor(self.member)
        second_group = Group.objects.create(name="second-grant-group")
        self.member.groups.add(second_group)
        ObjectGroupEditorGrant.objects.create(
            content_type=self.grant.content_type,
            object_id=self.process.pk,
            group=second_group,
        )
        self.assertEqual(Process.objects.editable_by_user(self.member).count(), 1)

    def test_grants_do_not_cross_content_types(self):
        material = Material.objects.create(name="Unshared material", owner=self.owner)
        Process.objects.get_or_create(
            pk=material.pk, defaults={"name": "Same ID process", "owner": self.owner}
        )
        ObjectGroupEditorGrant.objects.get_or_create(
            content_type=self.grant.content_type,
            object_id=material.pk,
            group=self.group,
        )
        self.assertFalse(material.is_editable_by(self.member))
        self.assertFalse(UserCreatedObjectPermission().is_editor(self.member, material))

    def test_group_grant_is_unique_per_object(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ObjectGroupEditorGrant.objects.create(
                content_type=self.grant.content_type,
                object_id=self.process.pk,
                group=self.group,
            )

    def test_deleted_objects_have_no_stale_group_grants(self):
        self.process.delete()
        self.assertFalse(
            ObjectGroupEditorGrant.objects.filter(pk=self.grant.pk).exists()
        )

    def test_deleted_groups_have_no_stale_group_grants(self):
        self.group.delete()
        self.assertFalse(
            ObjectGroupEditorGrant.objects.filter(pk=self.grant.pk).exists()
        )

    def test_policy_still_requires_change_permission(self):
        self.group.permissions.clear()
        member = User.objects.get(pk=self.member.pk)
        self.assertTrue(self.process.is_editable_by(member))
        self.assertFalse(get_object_policy(member, self.process)["can_edit"])
        request = SimpleNamespace(user=member, method="PATCH", data={"name": "Changed"})
        self.assertFalse(
            UserCreatedObjectPermission().has_object_permission(
                request, None, self.process
            )
        )

    def test_staff_group_editor_keeps_existing_edit_access(self):
        self.group.permissions.clear()
        self.member.is_staff = True
        self.member.save()
        member = User.objects.get(pk=self.member.pk)
        request = SimpleNamespace(user=member, method="PATCH", data={"name": "Changed"})
        self.assertTrue(get_object_policy(member, self.process)["can_edit"])
        self.assertTrue(
            UserCreatedObjectPermission().has_object_permission(
                request, None, self.process
            )
        )

    def test_published_and_archived_objects_are_not_editable(self):
        for status in ("published", "archived"):
            with self.subTest(status=status):
                self.process.publication_status = status
                self.assertFalse(
                    get_object_policy(self.member, self.process)["can_edit"]
                )
                request = SimpleNamespace(
                    user=self.member, method="PATCH", data={"name": "Changed"}
                )
                self.assertFalse(
                    UserCreatedObjectPermission().has_object_permission(
                        request, None, self.process
                    )
                )

    def test_shared_edit_access_does_not_grant_ownership_or_moderation(self):
        policy = get_object_policy(self.member, self.process)
        self.assertTrue(policy["can_edit"])
        for key in (
            "can_delete",
            "can_approve",
            "can_reject",
            "can_transfer_ownership",
            "can_manage_editors",
        ):
            self.assertFalse(policy[key], key)
        for method, data in (
            ("DELETE", {}),
            ("PATCH", {"owner": self.member.pk}),
            ("PATCH", {"publication_status": "published"}),
        ):
            request = SimpleNamespace(user=self.member, method=method, data=data)
            self.assertFalse(
                UserCreatedObjectPermission().has_object_permission(
                    request, None, self.process
                )
            )

    def test_editor_checks_are_cached_per_model(self):
        permission = UserCreatedObjectPermission()
        self.assertTrue(permission.is_editor(self.member, self.process))
        with self.assertNumQueries(0):
            self.assertTrue(permission.is_editor(self.member, self.process))
            self.assertFalse(permission.is_editor(self.member, self.unshared))

    def test_group_member_can_open_and_save_shared_process(self):
        self.client.force_login(self.member)
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertEqual(response.status_code, 200)
        update_url = reverse("processes:process-update", kwargs={"pk": self.process.pk})
        response = self.client.post(
            f"{update_url}?section=overview",
            {
                "name": "Updated shared process",
                "short_description": "Saved through group access",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.process.refresh_from_db()
        self.assertEqual(self.process.short_description, "Saved through group access")
        self.assertEqual(self.process.owner, self.owner)
        self.assertEqual(self.process.publication_status, "private")

    def test_group_member_cannot_open_unshared_process(self):
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.unshared.get_absolute_url()).status_code, 403
        )


class SingleGroupWorkshopJourneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="workshop-contributor")
        cls.participant = User.objects.create_user(username="single-group-participant")
        cls.group = Group.objects.create(name="single-workshop-group")
        cls.group.permissions.add(
            *Permission.objects.filter(
                content_type__app_label="processes",
                codename__in=[
                    "access_app_feature",
                    "add_process",
                    "change_process",
                    "can_moderate_process",
                ],
            )
        )
        cls.participant.groups.set([cls.group])
        cls.process = Process.objects.create(
            name="Workshop review example", owner=cls.owner, publication_status="review"
        )
        ObjectGroupEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Process),
            object_id=cls.process.pk,
            group=cls.group,
            granted_by=cls.owner,
        )
        cls.material = Material.objects.create(
            name="Workshop published material",
            owner=cls.owner,
            publication_status="published",
        )

    def setUp(self):
        self.client.force_login(self.participant)

    def test_single_group_supports_private_draft_and_material_journey(self):
        self.assertFalse(self.participant.is_staff)
        self.assertFalse(self.participant.is_superuser)
        self.assertEqual(self.participant.groups.count(), 1)
        self.assertEqual(self.participant.user_permissions.count(), 0)
        response = self.client.post(
            reverse("processes:process-create"),
            {
                "name": "Group participant draft",
                "short_description": "Saved workshop summary",
            },
        )
        self.assertEqual(response.status_code, 302)
        process = Process.objects.get(name="Group participant draft")
        for section in ("inputs", "outputs"):
            response = self.client.post(
                f"{process.update_url}?section={section}",
                {
                    "process_materials-TOTAL_FORMS": "1",
                    "process_materials-INITIAL_FORMS": "0",
                    "process_materials-0-material": str(self.material.pk),
                    "process_materials-0-quantity_value": "",
                    "process_materials-0-quantity_unit": "",
                },
            )
            self.assertEqual(response.status_code, 302)
        process.refresh_from_db()
        self.assertEqual(process.owner, self.participant)
        self.assertEqual(process.publication_status, "private")
        self.assertEqual(process.process_materials.filter(role="input").count(), 1)
        self.assertEqual(process.process_materials.filter(role="output").count(), 1)
        response = self.client.get(process.get_absolute_url())
        self.assertContains(response, "Saved workshop summary")
        self.assertContains(response, "Workshop published material")

    def test_material_and_category_choices_need_no_extra_permissions(self):
        category = ProcessCategory.objects.create(
            name="Workshop published category",
            owner=self.owner,
            publication_status="published",
        )
        for route, obj in (
            ("material-autocomplete", self.material),
            ("processes:processcategory-autocomplete", category),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"q": obj.name})
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    obj.pk, [item["id"] for item in response.json()["results"]]
                )

    def test_review_list_and_editing_work_for_single_group_member(self):
        response = self.client.get(
            reverse("processes:process-list-review"), {"scope": "review"}
        )
        self.assertContains(response, self.process.name)
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "Jump to editing section")
        response = self.client.post(
            f"{self.process.update_url}?section=overview",
            {
                "name": self.process.name,
                "short_description": "Updated workshop example",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.process.refresh_from_db()
        self.assertEqual(self.process.short_description, "Updated workshop example")
        self.assertEqual(self.process.publication_status, "review")
        self.assertEqual(self.process.owner, self.owner)

    def test_moderation_keeps_four_eyes_rule(self):
        self.assertTrue(
            get_object_policy(self.participant, self.process)["can_approve"]
        )
        owned = Process.objects.create(
            name="Owned review process",
            owner=self.participant,
            publication_status="review",
        )
        self.assertFalse(get_object_policy(self.participant, owned)["can_approve"])
        self.assertFalse(get_object_policy(self.participant, owned)["can_reject"])

    def test_other_participants_private_drafts_are_not_listed_or_editable(self):
        private = Process.objects.create(
            name="Another participants draft", owner=self.owner
        )
        self.assertNotIn(
            private, filter_queryset_for_user(Process.objects.all(), self.participant)
        )
        self.assertFalse(get_object_policy(self.participant, private)["can_edit"])

    def test_membership_removal_revokes_editing_on_next_request(self):
        self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.participant.groups.remove(self.group)
        response = self.client.post(
            f"{self.process.update_url}?section=overview",
            {"name": self.process.name, "short_description": "Denied change"},
        )
        self.assertEqual(response.status_code, 403)
        self.process.refresh_from_db()
        self.assertNotEqual(self.process.short_description, "Denied change")
