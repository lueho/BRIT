from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals
from rest_framework.test import APIRequestFactory

from bibliography.models import Source
from materials.models import (
    ComponentMeasurement,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
)
from sources.waste_collection.models import Collection
from utils.properties.models import Property, Unit

from ..models import ReviewAction
from ..permissions import (
    UserCreatedObjectPermission,
    apply_scope_filter,
    build_scope_filter_params,
    filter_queryset_for_user,
    get_object_policy,
    user_is_moderator_for_model,
    visible_related_object,
)
from ..policy import decide, editable_queryset


def _permission(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


class AdapterPersonas(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.stranger = User.objects.create_user(username="stranger")
        self.editor = User.objects.create_user(username="editor")
        self.moderator = User.objects.create_user(username="moderator")
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.administrator = User.objects.create_user(username="policy-admin")

        self.owner.user_permissions.add(
            _permission(Property, "change_property"),
            _permission(Property, "delete_property"),
            _permission(Property, "add_property"),
        )
        self.editor.user_permissions.add(_permission(Property, "change_property"))
        self.moderator.user_permissions.add(
            _permission(Property, "can_moderate_property")
        )
        self.administrator.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )

        self.private = Property.objects.create(
            name="Priv", owner=self.owner, publication_status="private"
        )
        self.review = Property.objects.create(
            name="Rev", owner=self.owner, publication_status="review"
        )
        self.published = Property.objects.create(
            name="Pub", owner=self.owner, publication_status="published"
        )

    def _fresh(self, user):
        return User.objects.get(pk=user.pk)


class ObjectPolicyMappingTests(AdapterPersonas):
    def test_owner_with_change_gets_edit_flags(self):
        policy = get_object_policy(self.owner, self.private)
        self.assertTrue(policy["can_edit"])
        self.assertTrue(policy["can_read"])
        self.assertTrue(policy["can_delete"])
        self.assertTrue(policy["can_manage_samples"])
        self.assertTrue(policy["can_submit_review"])
        self.assertFalse(policy["is_moderator"])
        self.assertFalse(policy["is_admin"])

    def test_owner_without_change_cannot_edit(self):
        stranger_owned = Property.objects.create(
            name="No change", owner=self.stranger, publication_status="private"
        )
        policy = get_object_policy(self.stranger, stranger_owned)
        self.assertTrue(policy["is_owner"])
        self.assertTrue(policy["can_read"])
        self.assertFalse(policy["can_edit"])
        self.assertEqual(policy["reason_codes"]["edit"], "missing_model_permission")

    def test_grantee_without_change_has_no_management_rights(self):
        grantee = User.objects.create_user(username="grantee")
        self.private.add_editor(grantee)
        policy = get_object_policy(User.objects.get(pk=grantee.pk), self.private)
        self.assertTrue(policy["is_editor"])
        self.assertTrue(policy["can_read"])
        self.assertFalse(policy["can_edit"])
        self.assertEqual(policy["reason_codes"]["edit"], "missing_model_permission")
        self.assertFalse(policy["can_manage_editors"])
        self.assertFalse(policy["can_transfer_ownership"])

    def test_is_staff_is_informational_only(self):
        policy = get_object_policy(self.staff, self.private)
        self.assertTrue(policy["is_staff"])
        self.assertFalse(policy["is_admin"])
        self.assertFalse(policy["can_edit"])
        self.assertFalse(policy["can_read"])

    def test_moderator_can_view_review_activity_but_not_edit(self):
        policy = get_object_policy(self.moderator, self.review)
        self.assertTrue(policy["is_moderator"])
        self.assertTrue(policy["can_view_review_activity"])
        self.assertTrue(policy["can_comment_on_review"])
        self.assertTrue(policy["can_approve"])
        self.assertFalse(policy["can_edit"])

    def test_stranger_denied_review_activity(self):
        policy = get_object_policy(self.stranger, self.review)
        self.assertFalse(policy["can_read"])
        self.assertFalse(policy["can_view_review_activity"])
        self.assertFalse(policy["can_comment_on_review"])


class ScopedQuerysetAdapterTests(AdapterPersonas):
    def setUp(self):
        super().setUp()
        self.shared_group = Group.objects.create(name="shared-group")
        self.shared_editor = User.objects.create_user(username="shared-editor")
        self.shared_editor.groups.add(self.shared_group)
        self.shared_editor.user_permissions.add(
            _permission(Property, "change_property")
        )
        self.shared = Property.objects.create(
            name="Shared", owner=self.owner, publication_status="private"
        )
        self.shared.add_editor_group(self.shared_group)
        self.declined = Property.objects.create(
            name="Decl", owner=self.owner, publication_status="declined"
        )
        self.archived = Property.objects.create(
            name="Arch", owner=self.owner, publication_status="archived"
        )

    _MINE = {"Priv", "Rev", "Pub", "Shared", "Decl", "Arch"}

    def _names(self, user, scope):
        qs = apply_scope_filter(
            Property.objects.filter(name__in=self._MINE), scope, user=user
        )
        return set(qs.values_list("name", flat=True))

    def test_published_scope(self):
        self.assertEqual(self._names(self.stranger, "published"), {"Pub"})

    def test_none_scope_applies_general_visibility(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(self._names(self.owner, None), self._MINE)
        self.assertEqual(
            self._names(self.shared_editor, None), {"Pub", "Shared", "Arch"}
        )
        self.assertEqual(self._names(self.stranger, None), {"Pub", "Arch"})
        self.assertEqual(self._names(AnonymousUser(), None), {"Pub", "Arch"})

    def test_private_scope_contains_owned_and_shared(self):
        self.assertEqual(self._names(self.owner, "private"), self._MINE)
        self.assertEqual(self._names(self.shared_editor, "private"), {"Shared"})

    def test_owned_and_shared_refine_private(self):
        self.assertEqual(self._names(self.owner, "owned"), self._MINE)
        self.assertEqual(self._names(self.owner, "shared"), set())
        self.assertEqual(self._names(self.shared_editor, "owned"), set())
        self.assertEqual(self._names(self.shared_editor, "shared"), {"Shared"})

    def test_review_declined_archived_scopes(self):
        self.assertEqual(self._names(self.owner, "review"), {"Rev"})
        self.assertEqual(self._names(self.owner, "declined"), {"Decl"})
        self.assertEqual(self._names(self.owner, "archived"), {"Arch"})
        self.assertEqual(self._names(self.stranger, "declined"), set())

    def test_unknown_scope_returns_empty(self):
        self.assertEqual(self._names(self.owner, "bogus"), set())

    def test_filter_queryset_for_user_matches_visible(self):
        visible = filter_queryset_for_user(
            Property.objects.filter(name__in=self._MINE), self.stranger
        )
        self.assertEqual(set(visible.values_list("name", flat=True)), {"Pub", "Arch"})

    def test_visible_related_object(self):
        self.assertIs(visible_related_object(self.private, self.owner), self.private)
        self.assertIsNone(visible_related_object(self.private, self.stranger))

    def test_build_scope_filter_params(self):
        self.assertEqual(build_scope_filter_params("private", self.owner), {})
        self.assertEqual(
            build_scope_filter_params("review", self.owner),
            {"publication_status": ["review"]},
        )
        self.assertEqual(
            build_scope_filter_params("published", self.owner),
            {"publication_status": ["published"]},
        )

    def test_manager_access_methods_delegate(self):
        self.assertIn(
            self.shared,
            Property.objects.accessible_by_user(self.shared_editor),
        )
        self.assertIn(self.private, Property.objects.editable_by_user(self.owner))
        self.assertIn(
            self.shared, Property.objects.editable_by_user(self.shared_editor)
        )
        self.assertNotIn(self.published, Property.objects.editable_by_user(self.owner))
        self.assertIn(self.review, Property.objects.reviewable_by_user(self.moderator))
        self.assertEqual(list(Property.objects.reviewable_by_user(self.staff)), [])

    def test_revoked_grant_stops_edit_on_next_evaluation(self):
        self.shared.add_editor(self.editor)
        self.assertTrue(decide(self.editor, "edit", self.shared).allowed)
        self.shared.remove_editor(self.editor)
        self.assertFalse(decide(self._fresh(self.editor), "edit", self.shared).allowed)


class DrfPermissionAdapterTests(AdapterPersonas):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.permission = UserCreatedObjectPermission()

    def _request(self, method, user, data=None):
        request = getattr(self.factory, method.lower())(
            "/fake/", data=data or {}, format="json"
        )
        request.data = data or {}
        request.user = user
        return request

    def _view(self, action):
        return SimpleNamespace(action=action, queryset=Property.objects.all())

    def test_owner_patch_without_change_denied(self):
        request = self._request("patch", self.stranger)
        own = Property.objects.create(
            name="Own", owner=self.stranger, publication_status="private"
        )
        self.assertFalse(
            self.permission.has_object_permission(
                request, self._view("partial_update"), own
            )
        )

    def test_owner_patch_with_change_allowed(self):
        request = self._request("patch", self.owner)
        self.assertTrue(
            self.permission.has_object_permission(
                request, self._view("partial_update"), self.private
            )
        )

    def test_editor_with_change_edits_review_object(self):
        self.review.add_editor(self.editor)
        request = self._request("patch", self._fresh(self.editor))
        self.assertTrue(
            self.permission.has_object_permission(
                request, self._view("partial_update"), self.review
            )
        )

    def test_payload_with_owner_or_status_rejected(self):
        self.review.add_editor(self.editor)
        for payload in (
            {"owner": self.stranger.pk},
            {"publication_status": "published"},
            {"name": "x", "owner": self.stranger.pk},
        ):
            request = self._request("patch", self.editor, data=payload)
            self.assertFalse(
                self.permission.has_object_permission(
                    request, self._view("partial_update"), self.review
                )
            )

    def test_read_maps_to_policy_read(self):
        view = self._view("retrieve")
        self.assertTrue(
            self.permission.has_object_permission(
                self._request("get", self.stranger), view, self.published
            )
        )
        self.assertFalse(
            self.permission.has_object_permission(
                self._request("get", self.stranger), view, self.private
            )
        )

    def test_named_review_actions_map_to_policy(self):
        view = self._view("approve")
        request = self._request("post", self.moderator)
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.review)
        )
        self.assertFalse(
            self.permission.has_object_permission(
                self._request("post", self.owner), view, self.review
            )
        )

    def test_comment_action_maps_to_comment_on_review(self):
        view = self._view("add_review_comment")
        self.assertTrue(
            self.permission.has_object_permission(
                self._request("post", self.moderator), view, self.review
            )
        )
        self.assertFalse(
            self.permission.has_object_permission(
                self._request("post", self.stranger), view, self.review
            )
        )

    def test_unmapped_custom_action_denied_at_object_level(self):
        view = self._view("custom_action")
        self.assertFalse(
            self.permission.has_object_permission(
                self._request("post", self.owner), view, self.private
            )
        )


class ModeratorHelperTests(AdapterPersonas):
    def test_moderator_helper_ignores_is_staff(self):
        self.assertTrue(user_is_moderator_for_model(self.moderator, Property))
        self.assertFalse(user_is_moderator_for_model(self.staff, Property))
        self.assertTrue(user_is_moderator_for_model(self.administrator, Property))


class EvidenceAttachmentPolicyTests(TestCase):
    """MaterialPropertyValue/ComponentMeasurement independent-evidence rules."""

    def setUp(self):
        self.owner = User.objects.create(username="owner")
        self.contributor = User.objects.create(username="contributor")
        for model, codename in (
            (MaterialPropertyValue, "add_materialpropertyvalue"),
            (ComponentMeasurement, "add_componentmeasurement"),
        ):
            self.contributor.user_permissions.add(_permission(model, codename))
        self.editor = User.objects.create(username="editor")
        self.editor.user_permissions.add(
            _permission(Sample, "change_sample"),
            _permission(MaterialPropertyValue, "add_materialpropertyvalue"),
        )

        self.material = Material.objects.create(
            name="M", owner=self.owner, publication_status="published"
        )
        self.published_sample = Sample.objects.create(
            name="Pub",
            owner=self.owner,
            material=self.material,
            publication_status="published",
        )
        self.private_sample = Sample.objects.create(
            name="Priv",
            owner=self.owner,
            material=self.material,
            publication_status="private",
        )
        self.unit = Unit.objects.create(name="g/kg", symbol="g/kg")
        self.group = MaterialComponentGroup.objects.create(name="G")
        self.component = MaterialComponent.objects.create(name="C")
        self.mproperty = MaterialProperty.objects.create(name="P", owner=self.owner)

    def test_mpv_attach_to_published_sample_requires_collaborator(self):
        decision = decide(
            self.contributor,
            "create",
            MaterialPropertyValue,
            parent=self.published_sample,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "insufficient_parent_access")

        self.owner.user_permissions.add(
            _permission(MaterialPropertyValue, "add_materialpropertyvalue")
        )
        self.assertTrue(
            decide(
                self._fresh(self.owner),
                "create",
                MaterialPropertyValue,
                parent=self.published_sample,
            ).allowed
        )

        self.published_sample.add_editor(self.editor)
        self.assertTrue(
            decide(
                self._fresh(self.editor),
                "create",
                MaterialPropertyValue,
                parent=self.published_sample,
            ).allowed
        )

    def test_cm_attach_to_published_sample_denied(self):
        self.assertFalse(
            decide(
                self.contributor,
                "create",
                ComponentMeasurement,
                parent=self.published_sample,
            ).allowed
        )

    def test_evidence_on_private_parent_needs_edit(self):
        self.assertFalse(
            decide(
                self.contributor,
                "create",
                MaterialPropertyValue,
                parent=self.private_sample,
            ).allowed
        )
        self.private_sample.add_editor(self.editor)
        self.assertTrue(
            decide(
                self._fresh(self.editor),
                "create",
                MaterialPropertyValue,
                parent=self.private_sample,
            ).allowed
        )

    def _fresh(self, user):
        return User.objects.get(pk=user.pk)

    def test_parent_editor_cannot_edit_foreign_measurement(self):
        cm_owner = User.objects.create(username="cm-owner")
        cm_owner.user_permissions.add(
            _permission(ComponentMeasurement, "add_componentmeasurement")
        )
        measurement = ComponentMeasurement.objects.create(
            owner=cm_owner,
            sample=self.private_sample,
            component=self.component,
            group=self.group,
            unit=self.unit,
            average=Decimal("5"),
            publication_status="private",
        )
        self.private_sample.add_editor(self.editor)
        self.assertFalse(decide(self.editor, "edit", measurement).allowed)

    def test_evidence_visibility_follows_own_state(self):
        mpv = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.published_sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )
        self.assertFalse(decide(self.contributor, "read", mpv).allowed)
        mpv.publication_status = "published"
        mpv.save()
        self.assertTrue(decide(self.contributor, "read", mpv).allowed)

    def test_wrong_parent_type_denied(self):
        bad_parents = [
            Property.objects.create(name="P", owner=self.owner),
            Source.objects.create(title="S", owner=self.owner),
            Property.objects.create(name="OP", owner=self.contributor),
        ]
        for bad_parent in bad_parents:
            decision = decide(
                self.contributor,
                "create",
                MaterialPropertyValue,
                parent=bad_parent,
            )
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.reason, "invalid_parent")

    def test_unsaved_parent_denied(self):
        unsaved = Sample(name="unsaved", owner=self.owner, material=self.material)
        decision = decide(
            self.contributor,
            "create",
            MaterialPropertyValue,
            parent=unsaved,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")

    def test_parent_on_model_without_attachment_path_denied(self):
        decision = decide(self.owner, "create", Property, parent=self.published_sample)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")

    def test_acpv_mixed_or_empty_parents_denied(self):
        from sources.waste_collection.models import (
            AggregatedCollectionPropertyValue,
        )

        contributor = User.objects.create(username="acpv-contributor")
        contributor.user_permissions.add(
            _permission(
                AggregatedCollectionPropertyValue,
                "add_aggregatedcollectionpropertyvalue",
            )
        )
        collection = Collection.objects.create(
            name="C", owner=self.owner, publication_status="published"
        )
        wrong = Property.objects.create(name="P", owner=self.owner)

        decision = decide(
            contributor,
            "create",
            AggregatedCollectionPropertyValue,
            parent=[collection, wrong],
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")

        decision = decide(
            contributor,
            "create",
            AggregatedCollectionPropertyValue,
            parent=[collection],
        )
        self.assertTrue(decision.allowed, msg=decision.reason)

        decision = decide(
            contributor,
            "create",
            AggregatedCollectionPropertyValue,
            parent=[],
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")


class WorkspaceNavAndAccessModalTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.editor = User.objects.create_user(username="editor")
        self.stranger = User.objects.create_user(username="stranger")
        self.source = Source.objects.create(
            owner=self.owner, title="Shared source", publication_status="private"
        )
        self.source.add_editor(self.editor)

    def test_workspace_nav_renders_on_private_list(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("source-list-owned"), follow=True)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("All workspace records", content)
        self.assertIn("Owned by me", content)
        self.assertIn("Shared with me", content)

    def test_owned_and_shared_scope_params(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("source-list-owned"), {"scope": "shared"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared source")

        response = self.client.get(
            reverse("source-list-owned"), {"scope": "owned"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Shared source")

    def test_your_access_modal_owner(self):
        self.client.force_login(self.owner)
        ct = ContentType.objects.get_for_model(Source)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={"content_type_id": ct.pk, "object_id": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("owner", response.content.decode())

    def test_your_access_modal_editor_sees_own_route_only(self):
        self.client.force_login(self.editor)
        ct = ContentType.objects.get_for_model(Source)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={"content_type_id": ct.pk, "object_id": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("direct edit grant", content)

    def test_your_access_modal_stranger_denied(self):
        self.client.force_login(self.stranger)
        ct = ContentType.objects.get_for_model(Source)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={"content_type_id": ct.pk, "object_id": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_your_access_modal_requires_login(self):
        ct = ContentType.objects.get_for_model(Source)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={"content_type_id": ct.pk, "object_id": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 302)


class EditableQuerysetMatrixTests(TestCase):
    """``editable_queryset`` must agree with the object-level ``edit``
    decision for every persona and lifecycle state on every model kind."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.stranger = User.objects.create_user(username="stranger")
        self.editor = User.objects.create_user(username="editor")
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.admin_only = User.objects.create_user(username="admin-only")
        self.admin_change = User.objects.create_user(username="admin-change")
        self.inactive_owner = User.objects.create_user(
            username="inactive", is_active=False
        )
        self.admin_only.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        for user in (self.owner, self.editor, self.admin_change):
            user.user_permissions.add(_permission(Property, "change_property"))
        self.admin_change.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.inactive_owner.user_permissions.add(
            _permission(Property, "change_property")
        )

        self.rows = {}
        for status in ("private", "review", "declined", "published", "archived"):
            self.rows[status] = Property.objects.create(
                name=f"owner-{status}", owner=self.owner, publication_status=status
            )
        self.shared_private = Property.objects.create(
            name="shared", owner=self.stranger, publication_status="private"
        )
        self.shared_private.add_editor(self.editor)

    def _editable_names(self, user):
        qs = Property.objects.filter(
            pk__in=[r.pk for r in self.rows.values()] + [self.shared_private.pk]
        )
        return set(editable_queryset(user, qs).values_list("name", flat=True))

    def _assert_edit_agreement(self, user, obj, expected):
        qs = Property.objects.filter(pk=obj.pk)
        editable = editable_queryset(user, qs)
        self.assertEqual(
            editable.exists(),
            expected,
            msg=f"editable_queryset mismatch for {user} on {obj.name}",
        )
        self.assertEqual(
            decide(user, "edit", obj).allowed,
            expected,
            msg=f"decide/edit mismatch for {user} on {obj.name}",
        )

    def test_owner_with_change_across_states(self):
        expected = {
            "private": True,
            "review": True,
            "declined": True,
            "published": False,
            "archived": False,
        }
        for status, obj in self.rows.items():
            self._assert_edit_agreement(self.owner, obj, expected[status])
        self.assertEqual(
            self._editable_names(self.owner),
            {"owner-private", "owner-review", "owner-declined"},
        )

    def test_owner_without_change_gets_nothing(self):
        for obj in self.rows.values():
            self._assert_edit_agreement(self.stranger, obj, False)
        decision = decide(self.stranger, "edit", self.shared_private)
        self.assertEqual(decision.reason, "missing_model_permission")

    def test_editor_with_change_on_granted_row(self):
        self._assert_edit_agreement(self.editor, self.shared_private, True)

    def test_admin_permission_without_change_cannot_edit(self):
        for obj in self.rows.values():
            self._assert_edit_agreement(self.admin_only, obj, False)
        decision = decide(self.admin_only, "edit", self.rows["private"])
        self.assertEqual(decision.reason, "missing_model_permission")
        self.assertEqual(self._editable_names(self.admin_only), set())

    def test_admin_with_change_edits_all_editable_states(self):
        self._assert_edit_agreement(self.admin_change, self.rows["private"], True)
        self._assert_edit_agreement(self.admin_change, self.rows["published"], False)
        self.assertEqual(
            self._editable_names(self.admin_change),
            {"owner-private", "owner-review", "owner-declined", "shared"},
        )

    def test_staff_only_cannot_edit(self):
        for obj in self.rows.values():
            self._assert_edit_agreement(self.staff, obj, False)

    def test_inactive_owner_cannot_edit(self):
        own_private = Property.objects.create(
            name="inactive-own",
            owner=self.inactive_owner,
            publication_status="private",
        )
        self._assert_edit_agreement(self.inactive_owner, own_private, False)

    def test_owned_child_follows_parent_editability(self):
        from bibliography.models import Author, SourceAuthor

        for user in (self.owner, self.editor):
            user.user_permissions.add(_permission(Source, "change_source"))
        source = Source.objects.create(
            title="S", owner=self.owner, publication_status="private"
        )
        author = Author.objects.create(
            owner=self.owner, first_names="A", last_names="B"
        )
        child = SourceAuthor.objects.create(source=source, author=author, position=1)

        qs = SourceAuthor.objects.filter(pk=child.pk)
        self.assertTrue(editable_queryset(self.owner, qs).exists())
        source.add_editor(self.editor)
        fresh_editor = User.objects.get(pk=self.editor.pk)
        self.assertTrue(editable_queryset(fresh_editor, qs).exists())
        self.assertFalse(editable_queryset(self.stranger, qs).exists())

        source.publication_status = "published"
        source.save()
        self.assertFalse(editable_queryset(self.owner, qs).exists())
        self.assertFalse(editable_queryset(fresh_editor, qs).exists())

    def test_catalogue_model_edit_follows_change_capability(self):
        from sources.roadside_trees.models import HamburgRoadsideTrees

        row = HamburgRoadsideTrees.objects.create()
        change_perm = Permission.objects.get(
            codename="change_hamburgroadsidetrees",
            content_type=ContentType.objects.get_for_model(HamburgRoadsideTrees),
        )
        qs = HamburgRoadsideTrees.objects.filter(pk=row.pk)

        self.assertFalse(editable_queryset(self.stranger, qs).exists())
        self.assertFalse(decide(self.stranger, "edit", row).allowed)
        self.stranger.user_permissions.add(change_perm)
        stranger = User.objects.get(pk=self.stranger.pk)
        self.assertTrue(editable_queryset(stranger, qs).exists())
        self.assertTrue(decide(stranger, "edit", row).allowed)

    def test_unregistered_model_queryset_is_empty(self):
        self.assertFalse(editable_queryset(self.owner, Group.objects.all()).exists())


class SelectOptionsVisibilityTests(TestCase):
    """Post-create option refresh uses read visibility, not a model view gate."""

    def setUp(self):
        from sources.waste_collection.models import Collector

        self.creator = User.objects.create_user(username="creator")
        self.creator.user_permissions.add(_permission(Collector, "add_collector"))
        self.other = User.objects.create_user(username="other")
        self.foreign_private = Collector.objects.create(
            name="ForeignPrivate", owner=self.other, publication_status="private"
        )
        self.published = Collector.objects.create(
            name="PublishedCollector",
            owner=self.other,
            publication_status="published",
        )

    def test_options_visible_without_view_permission(self):
        self.client.force_login(self.creator)
        response = self.client.get(reverse("collector-options"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("PublishedCollector", content)
        self.assertNotIn("ForeignPrivate", content)

    def test_options_anonymous_sees_published_only(self):
        response = self.client.get(reverse("collector-options"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("PublishedCollector", content)
        self.assertNotIn("ForeignPrivate", content)


class DrfAdapterParityTests(AdapterPersonas):
    """The same request/object must produce the same decision through
    ``UserCreatedObjectPermission`` and ``HasModelPermission``."""

    def setUp(self):
        super().setUp()
        from utils.permissions import HasModelPermission

        self.factory = APIRequestFactory()
        self.uco = UserCreatedObjectPermission()
        self.hmp = HasModelPermission()

    def _request(self, method, user, data=None):
        request = getattr(self.factory, method.lower())(
            "/fake/", data=data or {}, format="json"
        )
        request.data = data or {}
        request.user = user
        return request

    def _view(self, action):
        return SimpleNamespace(
            action=action,
            queryset=Property.objects.all(),
            permission_required={
                "list": None,
                "retrieve": None,
                "create": "utils_properties.add_property",
                "update": "utils_properties.change_property",
                "partial_update": "utils_properties.change_property",
                "destroy": "utils_properties.delete_property",
                "custom_mutation": None,
            },
        )

    def _parity(self, method, action, user, obj, data=None):
        view = self._view(action)
        request = self._request(method, user, data=data)
        uco_result = self.uco.has_object_permission(request, view, obj)
        hmp_result = self.hmp.has_object_permission(request, view, obj)
        self.assertEqual(uco_result, hmp_result)
        return uco_result

    def test_same_decision_through_both_adapters(self):
        self.assertTrue(
            self._parity("patch", "partial_update", self.owner, self.private)
        )
        self.assertFalse(
            self._parity("patch", "partial_update", self.stranger, self.private)
        )
        self.assertTrue(self._parity("get", "retrieve", self.stranger, self.published))
        self.assertFalse(self._parity("get", "retrieve", self.stranger, self.private))
        self.assertTrue(self._parity("post", "approve", self.moderator, self.review))

    def test_unknown_registered_mutation_denied_by_both_adapters(self):
        self.assertFalse(
            self._parity("post", "custom_mutation", self.owner, self.private)
        )
        view = self._view("custom_mutation")
        self.assertFalse(
            self.hmp.has_permission(self._request("post", self.stranger), view)
        )

    def test_forbidden_payload_rejected_by_both_adapters(self):
        self.review.add_editor(self.editor)
        payload = {"name": "x", "publication_status": "published"}
        self.assertFalse(
            self._parity(
                "patch",
                "partial_update",
                self._fresh(self.editor),
                self.review,
                data=payload,
            )
        )


class ReviewActivityHttpTests(TestCase):
    """HTTP-level review detail/comment access follows the shared policy."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.editor = User.objects.create_user(username="editor")
        self.group_editor = User.objects.create_user(username="group-editor")
        self.group = Group.objects.create(name="review-editors")
        self.group.user_set.add(self.group_editor)
        self.moderator = User.objects.create_user(username="moderator")
        self.moderator.user_permissions.add(
            _permission(Collection, "can_moderate_collection")
        )
        self.stranger = User.objects.create_user(username="stranger")
        self.inactive = User.objects.create_user(username="inactive")
        self.collection = Collection.objects.create(
            name="Review Collection",
            owner=self.owner,
            publication_status="review",
        )
        self.collection.add_editor(self.editor)
        self.collection.add_editor_group(self.group)
        self.collection.add_editor(self.inactive)
        self.inactive.is_active = False
        self.inactive.save()
        self.ct_id = ContentType.objects.get_for_model(Collection).pk

    def _detail_url(self):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.collection.pk,
            },
        )

    def _comment_url(self):
        return reverse(
            "object_management:add_review_comment",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.collection.pk,
            },
        )

    def test_direct_and_group_editors_get_review_detail(self):
        for user in (self.owner, self.editor, self.group_editor, self.moderator):
            self.client.force_login(user)
            response = self.client.get(self._detail_url())
            self.assertEqual(response.status_code, 200)

    def test_stranger_and_inactive_denied_review_detail(self):
        for user in (self.stranger, self.inactive):
            self.client.force_login(user)
            response = self.client.get(self._detail_url())
            self.assertEqual(response.status_code, 403)
        response = self.client.get(self._detail_url())
        self.assertIn(response.status_code, (302, 403))

    def test_editor_post_comment(self):
        self.client.force_login(self.editor)
        response = self.client.post(self._comment_url(), {"message": "Looks good"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.ct_id,
                object_id=self.collection.pk,
                comment="Looks good",
            ).exists()
        )

    def test_stranger_post_comment_denied_without_row(self):
        self.client.force_login(self.stranger)
        response = self.client.post(self._comment_url(), {"message": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type_id=self.ct_id, object_id=self.collection.pk
            ).exists()
        )

    def test_history_retained_across_decline_and_withdraw(self):
        self.client.force_login(self.moderator)
        self.client.post(self._comment_url(), {"message": "needs work"})
        with mute_signals(post_save, pre_save):
            response = self.client.post(
                reverse(
                    "object_management:reject_item",
                    kwargs={
                        "content_type_id": self.ct_id,
                        "object_id": self.collection.pk,
                    },
                ),
                {"message": "declined"},
            )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.publication_status, "declined")
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.ct_id,
                object_id=self.collection.pk,
                comment="needs work",
            ).exists()
        )

        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(
                reverse(
                    "object_management:withdraw_from_review",
                    kwargs={
                        "content_type_id": self.ct_id,
                        "object_id": self.collection.pk,
                    },
                )
            )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.publication_status, "private")
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.ct_id, object_id=self.collection.pk
            ).exists()
        )
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)
