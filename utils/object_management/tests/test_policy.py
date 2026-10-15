from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.test import TestCase

from utils.properties.models import Property

from ..models import ReviewAction, UserCreatedObject
from ..policy import (
    Decision,
    capabilities,
    decide,
    object_access_routes,
    reviewable_queryset,
    scope_queryset,
    visible_queryset,
)


class PolicyDecisionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.regular = User.objects.create_user(username="regular")
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.moderator = User.objects.create_user(username="moderator")
        self.editor = User.objects.create_user(username="editor")
        self.group_editor = User.objects.create_user(username="group-editor")
        self.contributor = User.objects.create_user(username="contributor")
        self.administrator = User.objects.create_user(username="administrator")
        self.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="pw"
        )

        self.property_ct = ContentType.objects.get_for_model(Property)
        self.moderate_permission = Permission.objects.get(
            codename="can_moderate_property", content_type=self.property_ct
        )
        self.add_permission = Permission.objects.get(
            codename="add_property", content_type=self.property_ct
        )
        self.change_permission = Permission.objects.get(
            codename="change_property", content_type=self.property_ct
        )
        self.delete_permission = Permission.objects.get(
            codename="delete_property", content_type=self.property_ct
        )
        self.administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )

        self.moderator.user_permissions.add(self.moderate_permission)
        self.administrator.user_permissions.add(self.administer_permission)
        self.contributor.user_permissions.add(
            self.add_permission, self.change_permission, self.delete_permission
        )

        self.private_property = self._property(UserCreatedObject.STATUS_PRIVATE)
        self.review_property = self._property(UserCreatedObject.STATUS_REVIEW)
        self.published_property = self._property(UserCreatedObject.STATUS_PUBLISHED)
        self.declined_property = self._property(UserCreatedObject.STATUS_DECLINED)
        self.archived_property = self._property(UserCreatedObject.STATUS_ARCHIVED)

    def _property(self, status, owner=None, name=None):
        return Property.objects.create(
            name=name or f"Property {status}",
            owner=owner or self.owner,
            publication_status=status,
        )

    def _fresh(self, user):
        return User.objects.get(pk=user.pk)

    def assertDenied(self, decision, reason=None):
        self.assertIsInstance(decision, Decision)
        self.assertFalse(decision.allowed)
        if reason is not None:
            self.assertEqual(decision.reason, reason)

    def assertAllowed(self, decision):
        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed")

    def test_anonymous_reads_published_but_not_private(self):
        anonymous = AnonymousUser()
        self.assertAllowed(decide(anonymous, "read", self.published_property))
        self.assertDenied(
            decide(anonymous, "read", self.private_property),
            "authentication_required",
        )

    def test_inactive_users_receive_no_privileged_access(self):
        inactive_owner = User.objects.create_user(
            username="inactive-owner", is_active=False
        )
        own_property = self._property(
            UserCreatedObject.STATUS_PRIVATE, owner=inactive_owner
        )
        self.assertDenied(decide(inactive_owner, "read", own_property))
        self.assertDenied(decide(inactive_owner, "create", Property))

        inactive_moderator = User.objects.create_user(
            username="inactive-moderator", is_active=False
        )
        inactive_moderator.user_permissions.add(self.moderate_permission)
        self.assertDenied(decide(inactive_moderator, "read", self.review_property))
        self.assertDenied(decide(inactive_moderator, "create", Property))

        inactive_superuser = User.objects.create_superuser(
            username="inactive-root",
            email="inactive-root@example.com",
            password="pw",
            is_active=False,
        )
        self.assertDenied(decide(inactive_superuser, "read", self.private_property))
        self.assertDenied(decide(inactive_superuser, "create", Property))

    def test_owner_without_change_permission_cannot_edit_in_editable_states(self):
        for prop in (
            self.private_property,
            self.review_property,
            self.declined_property,
        ):
            with self.subTest(status=prop.publication_status):
                self.assertDenied(
                    decide(self.owner, "edit", prop), "missing_model_permission"
                )

    def test_owner_with_change_permission_edits_editable_states_only(self):
        self.owner.user_permissions.add(self.change_permission)
        owner = self._fresh(self.owner)
        for prop in (
            self.private_property,
            self.review_property,
            self.declined_property,
        ):
            with self.subTest(status=prop.publication_status):
                self.assertAllowed(decide(owner, "edit", prop))
        for prop in (self.published_property, self.archived_property):
            with self.subTest(status=prop.publication_status):
                self.assertDenied(decide(owner, "edit", prop), "immutable_state")

    def test_staff_without_permissions_has_no_bypass(self):
        self.assertDenied(
            decide(self.staff, "create", Property), "missing_model_permission"
        )
        self.assertDenied(
            decide(self.staff, "read", self.private_property), "no_object_access"
        )
        self.assertDenied(
            decide(self.staff, "read", self.review_property), "no_object_access"
        )
        # Archived content is public historical data — the staff flag is not
        # needed for read access.
        self.assertAllowed(decide(self.staff, "read", self.archived_property))

    def test_moderator_reads_review_declined_and_archived_but_not_private(self):
        self.assertAllowed(decide(self.moderator, "read", self.review_property))
        self.assertAllowed(decide(self.moderator, "read", self.declined_property))
        self.assertAllowed(decide(self.moderator, "read", self.published_property))
        self.assertAllowed(decide(self.moderator, "read", self.archived_property))
        self.assertDenied(
            decide(self.moderator, "read", self.private_property),
            "no_object_access",
        )

    def test_moderator_cannot_edit_without_owner_or_editor_access(self):
        self.moderator.user_permissions.add(self.change_permission)
        moderator = self._fresh(self.moderator)
        self.assertDenied(
            decide(moderator, "edit", self.review_property), "no_object_access"
        )
        self.assertDenied(
            decide(moderator, "edit", self.declined_property), "no_object_access"
        )

    def test_direct_editor_grant_reads_without_change_and_edits_with_it(self):
        self.private_property.add_editor(self.editor)
        editor = self._fresh(self.editor)

        self.assertAllowed(decide(editor, "read", self.private_property))
        self.assertDenied(
            decide(editor, "edit", self.private_property),
            "missing_model_permission",
        )

        self.editor.user_permissions.add(self.change_permission)
        editor = self._fresh(self.editor)
        self.assertAllowed(decide(editor, "edit", self.private_property))

    def test_editor_grant_alone_grants_no_owner_or_moderator_actions(self):
        self.private_property.add_editor(self.editor)
        self.editor.user_permissions.add(self.change_permission, self.delete_permission)
        editor = self._fresh(self.editor)

        self.assertAllowed(decide(editor, "edit", self.private_property))
        self.assertDenied(
            decide(editor, "delete", self.private_property), "no_object_access"
        )
        self.assertDenied(
            decide(editor, "manage_editors", self.private_property),
            "no_object_access",
        )
        self.assertDenied(
            decide(editor, "transfer_ownership", self.private_property),
            "no_object_access",
        )
        self.assertDenied(
            decide(editor, "submit", self.private_property), "no_object_access"
        )
        self.assertDenied(
            decide(editor, "approve", self.review_property),
            "missing_model_permission",
        )

    def test_group_editor_grant_allows_read_and_gated_edit(self):
        group = Group.objects.create(name="private-property-editors")
        self.private_property.add_editor_group(group)
        self.group_editor.groups.add(group)
        editor = self._fresh(self.group_editor)

        self.assertAllowed(decide(editor, "read", self.private_property))
        self.assertDenied(
            decide(editor, "edit", self.private_property),
            "missing_model_permission",
        )

        self.group_editor.user_permissions.add(self.change_permission)
        editor = self._fresh(self.group_editor)
        self.assertAllowed(decide(editor, "edit", self.private_property))

    def test_group_membership_changes_apply_to_new_evaluations(self):
        group = Group.objects.create(name="membership-editors")
        self.private_property.add_editor_group(group)
        member = User.objects.create_user(username="member")

        self.assertDenied(decide(self._fresh(member), "read", self.private_property))

        member.groups.add(group)
        self.assertAllowed(decide(self._fresh(member), "read", self.private_property))

        member.groups.remove(group)
        self.assertDenied(decide(self._fresh(member), "read", self.private_property))

    def test_overlapping_direct_and_group_grants_are_independent(self):
        group = Group.objects.create(name="overlap-editors")
        self.editor.groups.add(group)
        self.private_property.add_editor(self.editor)
        self.private_property.add_editor_group(group)

        self.assertAllowed(
            decide(self._fresh(self.editor), "read", self.private_property)
        )

        self.private_property.remove_editor(self.editor)
        self.assertAllowed(
            decide(self._fresh(self.editor), "read", self.private_property)
        )

        self.private_property.remove_editor_group(group)
        self.assertDenied(
            decide(self._fresh(self.editor), "read", self.private_property)
        )

    def test_superuser_administers_but_cannot_edit_frozen_objects(self):
        for prop in (
            self.private_property,
            self.review_property,
            self.published_property,
            self.declined_property,
            self.archived_property,
        ):
            with self.subTest(action="read", status=prop.publication_status):
                self.assertAllowed(decide(self.superuser, "read", prop))

        for prop in (
            self.private_property,
            self.review_property,
            self.declined_property,
        ):
            with self.subTest(action="edit", status=prop.publication_status):
                self.assertAllowed(decide(self.superuser, "edit", prop))

        for prop in (self.published_property, self.archived_property):
            with self.subTest(action="edit", status=prop.publication_status):
                self.assertDenied(
                    decide(self.superuser, "edit", prop), "immutable_state"
                )

    def test_administer_objects_permission_grants_admin_without_staff(self):
        self.assertFalse(self.administrator.is_staff)
        self.assertFalse(self.administrator.is_superuser)
        self.assertAllowed(decide(self.administrator, "read", self.private_property))
        self.assertAllowed(
            decide(self.administrator, "manage_editors", self.private_property)
        )
        self.assertAllowed(decide(self.administrator, "approve", self.review_property))
        self.assertDenied(
            decide(self.administrator, "create", Property),
            "missing_model_permission",
        )

    def test_create_requires_active_user_with_add_permission(self):
        self.assertDenied(
            decide(AnonymousUser(), "create", Property),
            "authentication_required",
        )
        self.assertDenied(
            decide(self.regular, "create", Property),
            "missing_model_permission",
        )
        self.assertAllowed(decide(self.contributor, "create", Property))

        self.regular.user_permissions.add(self.add_permission)
        self.assertAllowed(decide(self._fresh(self.regular), "create", Property))

    def test_missing_update_url_does_not_change_edit_decision(self):
        self.owner.user_permissions.add(self.change_permission)
        owner = self._fresh(self.owner)
        self.assertAllowed(decide(owner, "edit", self.private_property))
        with patch.object(Property, "update_url", None):
            self.assertAllowed(decide(owner, "edit", self.private_property))

    def test_submit_requires_owner_and_private_or_declined(self):
        self.assertAllowed(decide(self.owner, "submit", self.private_property))
        self.assertAllowed(decide(self.owner, "submit", self.declined_property))
        self.assertDenied(
            decide(self.owner, "submit", self.review_property), "invalid_state"
        )
        self.assertDenied(
            decide(self.owner, "submit", self.published_property), "invalid_state"
        )
        self.assertDenied(
            decide(self.owner, "submit", self.archived_property), "invalid_state"
        )
        self.assertDenied(
            decide(self.regular, "submit", self.private_property),
            "no_object_access",
        )
        self.assertAllowed(decide(self.administrator, "submit", self.private_property))

    def test_withdraw_requires_owner_and_review_or_declined(self):
        self.assertAllowed(decide(self.owner, "withdraw", self.review_property))
        self.assertAllowed(decide(self.owner, "withdraw", self.declined_property))
        self.assertDenied(
            decide(self.owner, "withdraw", self.private_property),
            "invalid_state",
        )
        self.assertDenied(
            decide(self.owner, "withdraw", self.published_property),
            "invalid_state",
        )
        self.assertDenied(
            decide(self.regular, "withdraw", self.review_property),
            "no_object_access",
        )

    def test_approve_and_reject_require_moderator_and_four_eyes(self):
        self.assertAllowed(decide(self.moderator, "approve", self.review_property))
        self.assertAllowed(decide(self.moderator, "reject", self.review_property))
        self.assertDenied(
            decide(self.moderator, "approve", self.private_property),
            "invalid_state",
        )
        self.assertDenied(
            decide(self.regular, "approve", self.review_property),
            "missing_model_permission",
        )

        self.owner.user_permissions.add(self.moderate_permission)
        owner_moderator = self._fresh(self.owner)
        self.assertDenied(
            decide(owner_moderator, "approve", self.review_property),
            "four_eyes_required",
        )
        self.assertDenied(
            decide(owner_moderator, "reject", self.review_property),
            "four_eyes_required",
        )

    def test_archive_requires_published_and_owner_moderator_or_admin(self):
        self.assertAllowed(decide(self.owner, "archive", self.published_property))
        self.assertAllowed(decide(self.moderator, "archive", self.published_property))
        self.assertAllowed(
            decide(self.administrator, "archive", self.published_property)
        )
        self.assertDenied(
            decide(self.owner, "archive", self.private_property), "invalid_state"
        )
        self.assertDenied(
            decide(self.moderator, "archive", self.review_property),
            "invalid_state",
        )
        self.assertDenied(
            decide(self.regular, "archive", self.published_property),
            "no_object_access",
        )

    def test_duplicate_and_new_version_require_read_and_add(self):
        self.assertAllowed(
            decide(self.contributor, "duplicate", self.published_property)
        )
        self.assertAllowed(
            decide(self.contributor, "new_version", self.published_property)
        )
        contributor_owned_archived = self._property(
            UserCreatedObject.STATUS_ARCHIVED,
            owner=self.contributor,
            name="Contributor archived",
        )
        self.assertDenied(
            decide(self.contributor, "new_version", contributor_owned_archived),
            "immutable_state",
        )
        self.assertDenied(
            decide(self.contributor, "duplicate", self.private_property),
            "no_object_access",
        )
        self.assertDenied(
            decide(self.regular, "duplicate", self.published_property),
            "missing_model_permission",
        )
        self.assertDenied(
            decide(AnonymousUser(), "duplicate", self.published_property),
            "authentication_required",
        )

    def test_review_activity_access(self):
        self.assertAllowed(
            decide(self.owner, "view_review_activity", self.private_property)
        )
        self.assertAllowed(
            decide(self.owner, "comment_on_review", self.private_property)
        )
        self.assertAllowed(
            decide(self.moderator, "view_review_activity", self.review_property)
        )
        self.assertAllowed(
            decide(self.moderator, "comment_on_review", self.review_property)
        )
        self.assertDenied(
            decide(self.moderator, "view_review_activity", self.private_property)
        )
        self.assertDenied(
            decide(self.regular, "view_review_activity", self.review_property)
        )
        self.assertDenied(
            decide(AnonymousUser(), "comment_on_review", self.published_property),
            "authentication_required",
        )

        self.private_property.add_editor(self.editor)
        editor = self._fresh(self.editor)
        self.assertAllowed(
            decide(editor, "view_review_activity", self.private_property)
        )
        self.assertAllowed(decide(editor, "comment_on_review", self.private_property))

    def test_manage_editors_and_transfer_ownership_require_owner_or_admin(self):
        self.assertAllowed(decide(self.owner, "manage_editors", self.private_property))
        self.assertAllowed(
            decide(self.owner, "transfer_ownership", self.private_property)
        )
        self.assertAllowed(
            decide(self.administrator, "transfer_ownership", self.private_property)
        )
        self.assertDenied(
            decide(self.regular, "manage_editors", self.private_property),
            "no_object_access",
        )
        self.assertDenied(
            decide(self.moderator, "manage_editors", self.review_property),
            "no_object_access",
        )

    def test_unsupported_action_denies(self):
        self.assertDenied(
            decide(self.owner, "promote", self.private_property),
            "unsupported_action",
        )
        self.assertDenied(
            decide(self.owner, "create", self.private_property),
            "unsupported_action",
        )
        self.assertDenied(
            decide(self.contributor, "read", Property), "unsupported_action"
        )

    def test_unknown_publication_status_denies_everyone(self):
        bogus = self._property("unknown")
        for user in (self.owner, self.administrator, self.superuser):
            with self.subTest(user=user.username):
                self.assertDenied(decide(user, "read", bogus), "invalid_state")
                self.assertDenied(decide(user, "edit", bogus), "invalid_state")
                self.assertDenied(decide(user, "submit", bogus), "invalid_state")
                self.assertDenied(decide(user, "export", bogus), "invalid_state")

    def test_unsupported_model_denies(self):
        group = Group.objects.create(name="unsupported-target")
        self.assertDenied(decide(self.owner, "read", group), "unsupported_model")
        self.assertDenied(decide(self.owner, "read", object()), "unsupported_model")
        self.assertDenied(
            decide(self.owner, "read", UserCreatedObject), "unsupported_model"
        )
        self.assertDenied(
            decide(self.owner, "read", self.private_property, parent=object()),
            "unsupported_model",
        )
        self.assertAllowed(
            decide(
                self.owner,
                "read",
                self.published_property,
                parent=self.private_property,
            )
        )

    def test_decisions_do_not_depend_on_requests(self):
        decision = decide(self.owner, "read", self.private_property)
        self.assertAllowed(decision)


class PolicyCapabilitiesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="capabilities-owner")
        property_ct = ContentType.objects.get_for_model(Property)
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_property", content_type=property_ct)
        )
        self.property = Property.objects.create(
            name="Capabilities property",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_capabilities_returns_decisions_for_all_object_actions(self):
        owner = User.objects.get(pk=self.owner.pk)
        result = capabilities(owner, self.property)
        self.assertIsInstance(result, dict)
        self.assertIn("read", result)
        self.assertIn("edit", result)
        self.assertIn("archive", result)
        self.assertNotIn("create", result)
        for action, decision in result.items():
            with self.subTest(action=action):
                self.assertIsInstance(decision, Decision)
        self.assertTrue(result["read"].allowed)
        self.assertTrue(result["edit"].allowed)
        self.assertFalse(result["archive"].allowed)

    def test_capabilities_ignores_class_and_unsupported_targets(self):
        self.assertEqual(capabilities(self.owner, Property), {})
        self.assertEqual(capabilities(self.owner, object()), {})


class PolicyQuerysetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="qs-owner")
        self.regular = User.objects.create_user(username="qs-regular")
        self.staff = User.objects.create_user(username="qs-staff", is_staff=True)
        self.moderator = User.objects.create_user(username="qs-moderator")
        self.editor = User.objects.create_user(username="qs-editor")
        self.administrator = User.objects.create_user(username="qs-admin")
        self.superuser = User.objects.create_superuser(
            username="qs-root", email="qs-root@example.com", password="pw"
        )

        property_ct = ContentType.objects.get_for_model(Property)
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_property", content_type=property_ct
            )
        )
        administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        self.administrator.user_permissions.add(administer_permission)

        self.objects = {}
        for status, _label in (
            ("private", UserCreatedObject.STATUS_PRIVATE),
            ("review", UserCreatedObject.STATUS_REVIEW),
            ("published", UserCreatedObject.STATUS_PUBLISHED),
            ("declined", UserCreatedObject.STATUS_DECLINED),
            ("archived", UserCreatedObject.STATUS_ARCHIVED),
        ):
            self.objects[status] = Property.objects.create(
                name=f"QS {status}",
                owner=self.owner,
                publication_status=status,
            )

        self.objects["private"].add_editor(self.editor)
        self.objects["archived"].add_editor(self.editor)

        self.base_queryset = Property.objects.filter(owner=self.owner)

    def _pk_set(self, queryset):
        return set(queryset.values_list("pk", flat=True))

    def _expected_visibility(self, persona):
        objects = self.objects
        all_states = {
            objects["private"].pk,
            objects["review"].pk,
            objects["published"].pk,
            objects["declined"].pk,
            objects["archived"].pk,
        }
        if persona in ("owner", "administrator", "superuser"):
            return all_states
        if persona == "editor":
            return {
                objects["private"].pk,
                objects["published"].pk,
                objects["archived"].pk,
            }
        if persona == "moderator":
            return {
                objects["review"].pk,
                objects["published"].pk,
                objects["declined"].pk,
                objects["archived"].pk,
            }
        return {objects["published"].pk, objects["archived"].pk}

    def _persona_users(self):
        return {
            "anonymous": AnonymousUser(),
            "regular": self.regular,
            "staff": self.staff,
            "owner": self.owner,
            "editor": self.editor,
            "moderator": self.moderator,
            "administrator": self.administrator,
            "superuser": self.superuser,
        }

    def test_visible_queryset_matches_read_decisions(self):
        for persona, user in self._persona_users().items():
            expected = self._expected_visibility(persona)
            with self.subTest(persona=persona):
                visible = self._pk_set(visible_queryset(user, self.base_queryset))
                self.assertEqual(visible, expected)
                visible_list = list(visible_queryset(user, self.base_queryset))
                self.assertEqual(len(visible_list), len(expected))
                for status, obj in self.objects.items():
                    with self.subTest(persona=persona, status=status):
                        self.assertEqual(
                            decide(user, "read", obj).allowed,
                            obj.pk in expected,
                        )

    def test_visible_queryset_preserves_caller_filters(self):
        caller_filtered = self.base_queryset.exclude(pk=self.objects["published"].pk)
        visible = self._pk_set(visible_queryset(self.owner, caller_filtered))
        self.assertNotIn(self.objects["published"].pk, visible)
        self.assertEqual(len(visible), 4)

    def test_unsupported_queryset_is_empty(self):
        self.assertEqual(list(visible_queryset(self.owner, Group.objects.all())), [])
        self.assertEqual(list(scope_queryset(self.owner, Group.objects.all())), [])
        self.assertEqual(
            list(scope_queryset(self.owner, Group.objects.all(), "owned")), []
        )

    def test_scope_queryset_scopes(self):
        objects = self.objects
        cases = {
            "owner": {
                "published": {objects["published"].pk},
                "private": {
                    objects["private"].pk,
                    objects["review"].pk,
                    objects["published"].pk,
                    objects["declined"].pk,
                    objects["archived"].pk,
                },
                "owned": {
                    objects["private"].pk,
                    objects["review"].pk,
                    objects["published"].pk,
                    objects["declined"].pk,
                    objects["archived"].pk,
                },
                "shared": set(),
                "review": {objects["review"].pk},
                "declined": {objects["declined"].pk},
                "archived": {objects["archived"].pk},
            },
            "editor": {
                "published": {objects["published"].pk},
                "private": {objects["private"].pk, objects["archived"].pk},
                "owned": set(),
                "shared": {objects["private"].pk, objects["archived"].pk},
                "review": set(),
                "declined": set(),
                "archived": {objects["archived"].pk},
            },
            "moderator": {
                "published": {objects["published"].pk},
                "private": set(),
                "owned": set(),
                "shared": set(),
                "review": {objects["review"].pk},
                "declined": {objects["declined"].pk},
                "archived": {objects["archived"].pk},
            },
            "anonymous": {
                "published": {objects["published"].pk},
                "private": set(),
                "owned": set(),
                "shared": set(),
                "review": set(),
                "declined": set(),
                "archived": {objects["archived"].pk},
            },
        }
        users = self._persona_users()
        for persona, scopes in cases.items():
            for scope, expected in scopes.items():
                with self.subTest(persona=persona, scope=scope):
                    self.assertEqual(
                        self._pk_set(
                            scope_queryset(users[persona], self.base_queryset, scope)
                        ),
                        expected,
                    )

    def test_scope_queryset_unknown_scope_returns_nothing(self):
        for persona, user in self._persona_users().items():
            with self.subTest(persona=persona):
                self.assertEqual(
                    self._pk_set(
                        scope_queryset(user, self.base_queryset, "bogus-scope")
                    ),
                    set(),
                )

    def test_scope_queryset_none_scope_matches_visibility(self):
        for persona, user in self._persona_users().items():
            with self.subTest(persona=persona):
                self.assertEqual(
                    self._pk_set(scope_queryset(user, self.base_queryset, None)),
                    self._expected_visibility(persona),
                )

    def test_invalid_status_rows_are_excluded_from_visibility(self):
        bogus = Property.objects.create(
            name="QS bogus",
            owner=self.owner,
            publication_status="unknown",
        )
        for persona, user in self._persona_users().items():
            with self.subTest(persona=persona):
                self.assertNotIn(
                    bogus.pk,
                    self._pk_set(visible_queryset(user, self.base_queryset)),
                )
                for scope in ("private", "owned", None):
                    self.assertNotIn(
                        bogus.pk,
                        self._pk_set(scope_queryset(user, self.base_queryset, scope)),
                    )

    def test_scope_queryset_never_broadens_visibility(self):
        # Scopes intersect with visibility; they never widen it. Private and
        # review scopes stay empty for actors without matching access, while
        # the public historical scope legitimately includes archives.
        scoped = scope_queryset(self.regular, self.base_queryset, "private")
        self.assertEqual(list(scoped), [])
        scoped = scope_queryset(self.regular, self.base_queryset, "review")
        self.assertEqual(list(scoped), [])
        scoped = scope_queryset(self.regular, self.base_queryset, "archived")
        self.assertEqual(self._pk_set(scoped), {self.objects["archived"].pk})
        scoped = scope_queryset(
            self.regular,
            Property.objects.filter(publication_status="private"),
            None,
        )
        self.assertEqual(list(scoped), [])


class PolicyReviewFindingRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="finding-owner")
        self.moderator = User.objects.create_user(username="finding-moderator")
        self.editor = User.objects.create_user(username="finding-editor")
        property_ct = ContentType.objects.get_for_model(Property)
        self.moderate_permission = Permission.objects.get(
            codename="can_moderate_property", content_type=property_ct
        )
        self.moderator.user_permissions.add(self.moderate_permission)
        self.private_property = Property.objects.create(
            name="Finding private",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.review_property = Property.objects.create(
            name="Finding review",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

    def test_review_queue_excludes_moderators_own_submissions(self):
        own = Property.objects.create(
            name="Finding own review",
            owner=self.moderator,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        moderator = User.objects.get(pk=self.moderator.pk)
        queue = reviewable_queryset(
            moderator, Property.objects.filter(pk__in=[own.pk, self.review_property.pk])
        )
        self.assertEqual(list(queue), [self.review_property])
        self.assertFalse(decide(moderator, "reject", own).allowed)

    def test_access_routes_report_public_reads_for_anonymous_and_inactive(self):
        published = Property.objects.create(
            name="Finding published",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        archived = Property.objects.create(
            name="Finding archived",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_ARCHIVED,
        )
        inactive = User.objects.create_user(
            username="finding-inactive", is_active=False
        )
        for user in (AnonymousUser(), inactive):
            with self.subTest(user=user):
                self.assertEqual(
                    object_access_routes(user, published), ["published (public read)"]
                )
                self.assertEqual(
                    object_access_routes(user, archived),
                    ["archived (public historical read)"],
                )
                self.assertEqual(object_access_routes(user, self.private_property), [])

    def test_revoked_direct_grant_applies_to_cached_user_instance(self):
        self.private_property.add_editor(self.editor)
        editor = User.objects.get(pk=self.editor.pk)
        self.assertTrue(decide(editor, "read", self.private_property).allowed)

        self.private_property.remove_editor(self.editor)
        self.assertFalse(decide(editor, "read", self.private_property).allowed)

    def test_revoked_group_grant_and_membership_apply_to_cached_user_instance(self):
        group = Group.objects.create(name="finding-editors")
        self.private_property.add_editor_group(group)
        self.editor.groups.add(group)
        editor = User.objects.get(pk=self.editor.pk)
        self.assertTrue(decide(editor, "read", self.private_property).allowed)

        self.private_property.remove_editor_group(group)
        self.assertFalse(decide(editor, "read", self.private_property).allowed)

        self.private_property.add_editor_group(group)
        self.assertTrue(decide(editor, "read", self.private_property).allowed)
        User.objects.get(pk=self.editor.pk).groups.remove(group)
        self.assertFalse(decide(editor, "read", self.private_property).allowed)

    def test_unaudited_creator_or_last_modifier_cannot_approve(self):
        for field in ("created_by", "lastmodified_by"):
            with self.subTest(field=field):
                candidate = Property.objects.create(
                    name=f"Finding unaudited {field}",
                    owner=self.owner,
                    publication_status=UserCreatedObject.STATUS_REVIEW,
                )
                Property.objects.filter(pk=candidate.pk).update(
                    **{field: self.moderator}
                )
                candidate.refresh_from_db()
                self.assertFalse(
                    ReviewAction.objects.filter(object_id=candidate.pk).exists()
                )
                decision = decide(self.moderator, "approve", candidate)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "four_eyes_required")
        self.assertTrue(decide(self.moderator, "approve", self.review_property).allowed)

    def test_rolled_back_grant_does_not_survive_in_cached_user_instance(self):
        editor = User.objects.get(pk=self.editor.pk)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.private_property.add_editor(self.editor)
                self.assertTrue(decide(editor, "read", self.private_property).allowed)
                raise RuntimeError("rollback")
        self.assertFalse(decide(editor, "read", self.private_property).allowed)

    def test_editor_grants_are_not_cached_while_version_store_is_unavailable(self):
        class UnavailableCache:
            def get(self, *args, **kwargs):
                return None

            def add(self, *args, **kwargs):
                return False

            def set(self, *args, **kwargs):
                return None

        self.private_property.add_editor(self.editor)
        editor = User.objects.get(pk=self.editor.pk)
        with patch("django.core.cache.cache", UnavailableCache()):
            self.assertTrue(decide(editor, "read", self.private_property).allowed)
            self.private_property.remove_editor(self.editor)
            self.assertFalse(decide(editor, "read", self.private_property).allowed)
