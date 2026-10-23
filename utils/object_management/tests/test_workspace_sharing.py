"""Workspace sharing: canonical access-change service, recipient dialog,
and workspace discovery presentation."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import constants as message_levels
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Author, Source, SourceAuthor
from materials.models import AnalyticalMethod
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
)
from utils.object_management.registry import KIND_GENERATED, KIND_REVIEWABLE
from utils.object_management.services import (
    perform_access_change,
    perform_transition,
    record_comment,
)
from utils.object_management.templatetags.moderation_tags import workspace_scope_links
from utils.object_management.views import (
    BaseObjectAccessActionView,
    BulkManageAccessView,
)
from utils.properties.models import Unit


def _events(obj, action=None):
    qs = ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
    )
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class SharingFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._role_output = StringIO()
        with redirect_stdout(cls._role_output), redirect_stderr(cls._role_output):
            call_command("sync_roles", "--apply", stdout=cls._role_output)

    def setUp(self):
        self.owner = User.objects.create_user(username="share-owner")
        self.recipient = User.objects.create_user(username="share-recipient")
        self.other = User.objects.create_user(username="share-other")
        self.team = Group.objects.create(name="share-team")
        self.team.user_set.add(self.other)
        self.staff = User.objects.create_user(username="share-staff", is_staff=True)
        self.staff.groups.clear()
        self.inactive = User.objects.create_user(
            username="share-inactive", is_active=False
        )
        self.inactive.groups.clear()
        self.method = AnalyticalMethod.objects.create(
            owner=self.owner, name="Shared method", publication_status="private"
        )
        self.method_ct = ContentType.objects.get_for_model(AnalyticalMethod)

    def access_url(self, action="your_access_modal", obj=None):
        obj = self.method if obj is None else obj
        return reverse(
            f"object_management:{action}",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(obj).pk,
                "object_id": obj.pk,
            },
        )


class AccessChangeServiceTests(SharingFixture):
    """The canonical perform_access_change service must govern all five
    public mutations against a locked, freshly authorized target."""

    def test_transfer_preserves_new_owner_direct_grant(self):
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.client.post(
            reverse(
                "object_management:transfer_ownership",
                kwargs={
                    "content_type_id": self.method_ct.pk,
                    "object_id": self.method.pk,
                },
            ),
            {"new_owner": self.recipient.username},
        )
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.recipient)
        self.assertTrue(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.recipient
            ).exists()
        )

    def test_former_owner_keeps_prior_direct_grant_after_transfer(self):
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.owner,
            granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.client.post(
            reverse(
                "object_management:transfer_ownership",
                kwargs={
                    "content_type_id": self.method_ct.pk,
                    "object_id": self.method.pk,
                },
            ),
            {"new_owner": self.recipient.username},
        )
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.recipient)
        self.assertTrue(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.owner
            ).exists()
        )
        # The former owner still has edit access via the retained grant.
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("analyticalmethod-update", kwargs={"pk": self.method.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_all_user_actions_recheck_owner_after_advisory_gate(self):
        record_comment(self.owner, self.method, "Preserved through denial")
        history = list(_events(self.method).values())
        original = BaseObjectAccessActionView._resolve_user

        def resolve_then_transfer(view, username):
            recipient = original(view, username)
            AnalyticalMethod.objects.filter(pk=self.method.pk).update(owner=self.other)
            return recipient

        self.client.force_login(self.owner)
        for action in ("add_editor", "remove_editor", "transfer_ownership"):
            with self.subTest(action=action):
                AnalyticalMethod.objects.filter(pk=self.method.pk).update(
                    owner=self.owner
                )
                ObjectEditorGrant.for_object(self.method).delete()
                if action == "remove_editor":
                    self.method.add_editor(self.recipient, granted_by=self.owner)
                before_grants = list(ObjectEditorGrant.for_object(self.method).values())
                field = "new_owner" if action == "transfer_ownership" else "user"
                with patch.object(
                    BaseObjectAccessActionView, "_resolve_user", resolve_then_transfer
                ):
                    response = self.client.post(
                        self.access_url(action), {field: self.recipient.username}
                    )
                self.assertEqual(response.status_code, 403)
                self.method.refresh_from_db()
                self.assertEqual(self.method.owner_id, self.other.pk)
                self.assertEqual(self.method.content_revision, 1)
                self.assertEqual(list(_events(self.method).values()), history)
                self.assertEqual(
                    list(ObjectEditorGrant.for_object(self.method).values()),
                    before_grants,
                )

    def test_cached_administrator_revoked_after_gate_is_denied(self):
        admin = User.objects.create_user(username="sharing-race-admin")
        administrators = Group.objects.get(name="administrators")
        admin.groups.add(administrators)
        original = BaseObjectAccessActionView._resolve_user

        def resolve_then_revoke(view, username):
            self.assertTrue(
                view.request.user.has_perm("object_management.administer_objects")
            )
            recipient = original(view, username)
            admin.groups.remove(administrators)
            return recipient

        self.client.force_login(admin)
        with patch.object(
            BaseObjectAccessActionView, "_resolve_user", resolve_then_revoke
        ):
            response = self.client.post(
                self.access_url("add_editor"), {"user": self.recipient.username}
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ObjectEditorGrant.for_object(self.method).exists())

    def test_owner_deactivated_after_gate_is_denied(self):
        original = BaseObjectAccessActionView._resolve_user

        def resolve_then_deactivate(view, username):
            recipient = original(view, username)
            User.objects.filter(pk=self.owner.pk).update(is_active=False)
            return recipient

        self.client.force_login(self.owner)
        with patch.object(
            BaseObjectAccessActionView, "_resolve_user", resolve_then_deactivate
        ):
            response = self.client.post(
                self.access_url("add_editor"), {"user": self.recipient.username}
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ObjectEditorGrant.for_object(self.method).exists())

    def test_target_deleted_after_gate_returns_404(self):
        original = BaseObjectAccessActionView._resolve_user

        def resolve_then_delete(view, username):
            recipient = original(view, username)
            AnalyticalMethod.objects.filter(pk=self.method.pk).delete()
            return recipient

        self.client.force_login(self.owner)
        with patch.object(
            BaseObjectAccessActionView, "_resolve_user", resolve_then_delete
        ):
            response = self.client.post(
                self.access_url("add_editor"), {"user": self.recipient.username}
            )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ObjectEditorGrant.for_object(self.method).exists())

    def test_transfer_without_remaining_route_redirects_to_workspace(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.access_url("transfer_ownership"),
            {"new_owner": self.recipient.username},
        )
        self.assertRedirects(
            response,
            reverse("analyticalmethod-list-owned") + "?scope=private",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.get(self.method.get_absolute_url()).status_code, 403
        )

    def test_former_owner_retains_group_route(self):
        self.team.user_set.add(self.owner)
        self.method.add_editor_group(self.team, granted_by=self.owner)
        self.client.force_login(self.owner)
        response = self.client.post(
            self.access_url("transfer_ownership"),
            {"new_owner": self.recipient.username},
        )
        self.assertRedirects(response, self.method.get_absolute_url())
        self.assertEqual(self.client.get(self.access_url()).status_code, 200)


class YourAccessModalTests(SharingFixture):
    """The your-access modal explains the actor's own routes — and nothing
    else. It must not expose other users, grants, or management controls."""

    def _url(self):
        return reverse(
            "object_management:your_access_modal",
            kwargs={
                "content_type_id": self.method_ct.pk,
                "object_id": self.method.pk,
            },
        )

    def test_owner_gets_own_access_explanation(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "owner")

    def test_granted_editor_sees_direct_route_not_members(self):
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "edit grant")
        self.assertNotContains(response, "share-team")

    def test_readable_actor_without_edit_sees_explanation(self):
        self.method.publication_status = "published"
        self.method.save()
        self.client.force_login(self.other)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_invisible_foreign_source_403(self):
        self.client.force_login(self.other)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)

    def test_post_method_not_allowed(self):
        self.client.force_login(self.owner)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 405)


class WorkspaceScopeLinkTests(SharingFixture):
    """Filtered lists offer workspace scope navigation for authenticated
    actors; unknown scopes fail closed with no active entry."""

    def _workspace_nav_html(self, response):
        marker = 'id="workspace-nav"'
        self.assertIn(marker, response.content.decode())
        return response.content.decode().split(marker, 1)[1].split("</nav>", 1)[0]

    def test_workspace_nav_renders_three_scopes(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("analyticalmethod-list-owned"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All workspace records")
        self.assertContains(response, "Owned by me")
        self.assertContains(response, "Shared with me")

    def test_shared_scope_lists_grant_visible_records(self):
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=shared", follow=True
        )
        self.assertContains(response, "Shared method")

    def test_unknown_scope_no_active_entry(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=bogus", follow=True
        )
        self.assertEqual(response.status_code, 200)
        nav_html = self._workspace_nav_html(response)
        self.assertNotIn("nav-link active", nav_html)


class AccessChangeServiceUnitTests(SharingFixture):
    """Direct service contract: lock, fresh actor, recipient validation,
    atomic rollback — independent of any view."""

    def test_unknown_action_validation_error_no_writes(self):
        before = ObjectEditorGrant.objects.count()
        with self.assertRaises(ValidationError):
            perform_access_change(
                self.owner, self.method, "bogus_action", self.recipient
            )
        self.assertEqual(ObjectEditorGrant.objects.count(), before)
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.owner)

    def test_wrong_recipient_type_validation_error(self):
        before = ObjectEditorGrant.objects.count()
        with self.assertRaises(ValidationError):
            perform_access_change(self.owner, self.method, "add_editor", self.team)
        with self.assertRaises(ValidationError):
            perform_access_change(
                self.owner, self.method, "add_editor_group", self.recipient
            )
        self.assertEqual(ObjectEditorGrant.objects.count(), before)
        self.assertEqual(ObjectGroupEditorGrant.objects.count(), 0)

    def test_unsaved_recipient_validation_error(self):
        with self.assertRaises(ValidationError):
            perform_access_change(
                self.owner, self.method, "add_editor", User(username="ghost")
            )
        self.assertEqual(ObjectEditorGrant.objects.count(), 0)

    def test_deleted_recipient_validation_error(self):
        dead = User.objects.create_user(username="dead-user")
        dead_id = dead.pk
        dead.delete()
        dead.pk = dead_id
        with self.assertRaises(ValidationError):
            perform_access_change(self.owner, self.method, "add_editor", dead)
        self.assertEqual(ObjectEditorGrant.objects.count(), 0)

    def test_inactive_recipient_transfer_denied(self):
        with self.assertRaises(ValidationError):
            perform_access_change(
                self.owner, self.method, "transfer_ownership", self.inactive
            )
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.owner)

    def test_non_reviewable_target_rejected(self):
        # An owned child cannot gain independently governed grants.
        source = Source.objects.create(owner=self.owner, title="S")
        author = Author.objects.create(
            owner=self.owner, first_names="A", last_names="B"
        )
        row = SourceAuthor.objects.create(source=source, author=author, position=1)
        with self.assertRaises(ValidationError):
            perform_access_change(self.owner, row, "add_editor", self.recipient)
        self.assertEqual(ObjectEditorGrant.objects.count(), 0)

    def test_locked_classification_is_authoritative(self):
        with patch(
            "utils.object_management.services.record_policy",
            side_effect=[
                SimpleNamespace(kind=KIND_REVIEWABLE),
                SimpleNamespace(kind=KIND_GENERATED),
            ],
        ):
            with self.assertRaises(ValidationError):
                perform_access_change(
                    self.owner, self.method, "add_editor", self.recipient
                )
        self.assertFalse(ObjectEditorGrant.for_object(self.method).exists())

    def test_mid_change_failure_rolls_back_persisted_grant(self):
        # Patch the model helper so the grant is REALLY written inside the
        # transaction, then raise — the atomic boundary must roll it back.
        original = AnalyticalMethod.add_editor
        grant_seen = []

        def _writing_then_failing(inner_self, user, granted_by=None):
            grant = original(inner_self, user, granted_by=granted_by)
            self.assertTrue(ObjectEditorGrant.objects.filter(pk=grant.pk).exists())
            grant_seen.append(grant.pk)
            raise ValidationError("simulated downstream failure")

        before_rev = self.method.content_revision
        with patch.object(
            AnalyticalMethod,
            "add_editor",
            side_effect=_writing_then_failing,
            autospec=True,
        ):
            with self.assertRaises(ValidationError):
                perform_access_change(
                    self.owner, self.method, "add_editor", self.recipient
                )
        # The grant existed inside the boundary but was rolled back.
        self.assertTrue(grant_seen)
        self.assertFalse(ObjectEditorGrant.objects.filter(pk=grant_seen[0]).exists())
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.owner)
        self.assertEqual(self.method.content_revision, before_rev)

    def test_share_and_transfer_preserve_history_and_grants(self):
        comment = record_comment(self.owner, self.method, "Existing feedback")
        before_rev = self.method.content_revision
        before_history = list(
            ReviewAction.objects.filter(
                content_type=self.method_ct, object_id=self.method.pk
            ).values_list("pk", "action", "comment")
        )
        ObjectGroupEditorGrant.objects.create(
            content_object=self.method,
            group=self.team,
            granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        for name, data in (
            ("add_editor", {"user": self.recipient.username}),
            ("transfer_ownership", {"new_owner": self.recipient.username}),
        ):
            self.client.post(
                reverse(
                    f"object_management:{name}",
                    kwargs={
                        "content_type_id": self.method_ct.pk,
                        "object_id": self.method.pk,
                    },
                ),
                data,
            )
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.recipient)
        self.assertEqual(self.method.content_revision, before_rev)
        self.assertEqual(
            list(
                ReviewAction.objects.filter(
                    content_type=self.method_ct, object_id=self.method.pk
                ).values_list("pk", "action", "comment")
            ),
            before_history,
        )
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        # Every grant survives the transfer, including the new owner's.
        self.assertTrue(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.recipient
            ).exists()
        )
        self.assertTrue(
            ObjectGroupEditorGrant.objects.filter(
                object_id=self.method.pk, group=self.team
            ).exists()
        )


class BulkManageAccessPolicyTests(SharingFixture):
    def _post(self, action, items):
        return self.client.post(
            reverse("object_management:bulk_manage_access"),
            {
                "bulk_action": action,
                "username": self.recipient.username,
                "items": items,
            },
        )

    def test_bulk_stale_item_skipped_others_applied(self):
        stale = AnalyticalMethod.objects.create(
            owner=self.owner, name="Stale", publication_status="private"
        )
        original = BulkManageAccessView._resolve_objects

        def resolve_then_transfer(view, request):
            objects = list(original(view, request))
            AnalyticalMethod.objects.filter(pk=stale.pk).update(owner=self.other)
            return objects

        self.client.force_login(self.owner)
        with patch.object(
            BulkManageAccessView, "_resolve_objects", resolve_then_transfer
        ):
            response = self._post(
                "add_editor",
                [
                    f"{self.method_ct.pk}:{self.method.pk}",
                    f"{self.method_ct.pk}:{stale.pk}",
                ],
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.recipient
            ).exists()
        )
        self.assertFalse(
            ObjectEditorGrant.objects.filter(
                object_id=stale.pk, editor=self.recipient
            ).exists()
        )
        notices = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn(
            f"Added direct editor grants for {self.recipient.username} for 1 item(s).",
            notices,
        )
        self.assertIn("Skipped 1 item(s).", notices)

    def test_bulk_staff_only_denied(self):
        self.client.force_login(self.staff)
        response = self._post("add_editor", [f"{self.method_ct.pk}:{self.method.pk}"])
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.recipient
            ).exists()
        )


class WorkspaceScopeCoverageTests(SharingFixture):
    """Workspace discovery across overlap, revocation, and future membership."""

    def _list_ids(self, scope):
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + f"?scope={scope}",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        page_obj = response.context.get("page_obj")
        if page_obj is not None:
            return sorted(obj.pk for obj in page_obj.object_list)
        object_list = response.context.get("object_list") or []
        return sorted(obj.pk for obj in object_list)

    def test_overlap_shown_once_under_all_workspace(self):
        # Overlapping routes must not duplicate the recipient's row.
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.team.user_set.add(self.recipient)
        ObjectGroupEditorGrant.objects.create(
            content_object=self.method,
            group=self.team,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        # direct + group grants overlap: exactly one row, exactly once.
        self.assertEqual(self._list_ids("private"), [self.method.pk])
        self.assertEqual(self._list_ids("shared"), [self.method.pk])
        self.assertEqual(self._list_ids("owned"), [])

    def test_owned_excludes_granted_and_shared_excludes_owned(self):
        own = AnalyticalMethod.objects.create(
            owner=self.recipient, name="Own", publication_status="private"
        )
        # Redundant grant on an owned row must not leak into shared scope.
        ObjectEditorGrant.objects.create(
            content_object=own, editor=self.recipient, granted_by=self.owner
        )
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        self.assertEqual(sorted(self._list_ids("owned")), [own.pk])
        self.assertEqual(sorted(self._list_ids("shared")), [self.method.pk])
        self.assertEqual(
            sorted(self._list_ids("private")), sorted([own.pk, self.method.pk])
        )

    def test_foreign_private_and_published_not_in_workspace(self):
        AnalyticalMethod.objects.create(
            owner=self.other, name="Foreign", publication_status="private"
        )
        AnalyticalMethod.objects.create(
            owner=self.other, name="Public", publication_status="published"
        )
        self.client.force_login(self.recipient)
        self.assertEqual(self._list_ids("private"), [])
        self.assertEqual(self._list_ids("shared"), [])
        self.assertEqual(self._list_ids("owned"), [])

    def test_revocation_removes_shared_row_and_modal_denies(self):
        grant = ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        self.assertEqual(self._list_ids("shared"), [self.method.pk])
        modal_url = reverse(
            "object_management:your_access_modal",
            kwargs={
                "content_type_id": self.method_ct.pk,
                "object_id": self.method.pk,
            },
        )
        self.assertEqual(self.client.get(modal_url).status_code, 200)
        grant.delete()
        response = self.client.get(modal_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._list_ids("shared"), [])

    def test_future_member_gains_access_without_perm_change(self):
        ObjectGroupEditorGrant.objects.create(
            content_object=self.method,
            group=self.team,
            granted_by=self.owner,
        )
        late = User.objects.create_user(username="share-late")
        self.client.force_login(late)
        modal_url = reverse(
            "object_management:your_access_modal",
            kwargs={
                "content_type_id": self.method_ct.pk,
                "object_id": self.method.pk,
            },
        )
        self.assertEqual(self.client.get(modal_url).status_code, 403)
        self.team.user_set.add(late)
        self.assertEqual(self.client.get(modal_url).status_code, 200)
        self.assertEqual(self._list_ids("shared"), [self.method.pk])

    def test_removing_one_route_preserves_access_until_last_route_is_removed(self):
        direct = self.method.add_editor(self.recipient, granted_by=self.owner)
        self.team.user_set.add(self.recipient)
        self.method.add_editor_group(self.team, granted_by=self.owner)
        self.client.force_login(self.recipient)
        for remove_route in (
            lambda: None,
            direct.delete,
            lambda: self.team.user_set.remove(self.recipient),
        ):
            remove_route()
            remains = self.team.user_set.filter(pk=self.recipient.pk).exists()
            self.assertEqual(
                self._list_ids("shared"), [self.method.pk] if remains else []
            )
            self.assertEqual(
                self.client.get(self.method.get_absolute_url()).status_code,
                200 if remains else 403,
            )
            self.assertEqual(
                self.client.get(self.access_url()).status_code, 200 if remains else 403
            )

    def test_spoofed_actor_params_ignored(self):
        self.method.publication_status = "published"
        self.method.save()
        self.client.force_login(self.other)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={
                    "content_type_id": self.method_ct.pk,
                    "object_id": self.method.pk,
                },
            )
            + "?user=share-owner&group=share-team"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "share-team")
        self.assertNotContains(response, "edit grant")

    def test_unknown_content_type_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={
                    "content_type_id": 999999,
                    "object_id": self.method.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 404)


class WorkspaceScopeLinkUnitTests(TestCase):
    """Direct unit coverage for the workspace_scope_links tag: query
    preservation, stripped params, fragment, active state, inactive actor."""

    def _links(self, base_url, get_params="", user=None):
        request = RequestFactory().get(f"/list/?{get_params}")
        request.user = self.owner if user is None else user
        return workspace_scope_links({"request": request}, base_url)

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="nav-owner")

    def test_base_and_request_queries_merged_and_stripped(self):
        links = self._links(
            "/methods/?id=8&page=3&publication_status=review&next=%2Fx&base=kept#anchor",
            get_params="q=oak+%26+birch&ordering=-name&tag=a&tag=b&scope=shared&page=2&return_to=%2Fback",
        )
        by_label = {link["label"]: link for link in links}
        shared = by_label["Shared with me"]
        self.assertTrue(shared["active"])
        self.assertIn("#anchor", shared["url"])
        self.assertIn("base=kept", shared["url"])
        query = parse_qs(urlsplit(shared["url"]).query)
        self.assertEqual(query["q"], ["oak & birch"])
        self.assertEqual(query["ordering"], ["-name"])
        self.assertEqual(query["tag"], ["a", "b"])
        self.assertEqual(urlsplit(shared["url"]).path, "/methods/")
        # Multi-valued overlay preserved
        self.assertEqual(shared["url"].count("tag="), 2)
        # Stripped params gone (except the scope we set)
        for bad in ("id=", "page=", "publication_status=", "next=", "return_to="):
            self.assertNotIn(bad, shared["url"])
        self.assertIn("scope=shared", shared["url"])
        self.assertEqual(shared["url"].count("?"), 1)

    def test_default_active_is_private(self):
        links = self._links("/methods/")
        self.assertEqual(
            [link["label"] for link in links if link["active"]],
            ["All workspace records"],
        )

    def test_unknown_scope_no_active(self):
        for scope in ("bogus", ""):
            with self.subTest(scope=scope):
                links = self._links("/methods/", get_params=f"scope={scope}")
                self.assertFalse(any(link["active"] for link in links))

    def test_inactive_and_anonymous_no_links(self):
        inactive = User.objects.create_user(username="nav-inact", is_active=False)
        self.assertEqual(self._links("/methods/", user=inactive), [])
        self.assertEqual(self._links("/methods/", user=AnonymousUser()), [])


class AccessPrivacyAndWarningTests(SharingFixture):
    """Recipient dialog privacy: own routes only, escapes applied, warnings
    land at the right level."""

    def test_group_name_escaped_in_routes(self):
        evil = Group.objects.create(name="<script>alert(1)</script>")
        evil.user_set.add(self.recipient)
        ObjectGroupEditorGrant.objects.create(
            content_object=self.method, group=evil, granted_by=self.owner
        )
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={
                    "content_type_id": self.method_ct.pk,
                    "object_id": self.method.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert")
        self.assertContains(response, "&lt;script&gt;")

    def test_grant_warning_for_recipient_without_model_permission(self):
        self.recipient.groups.clear()
        self.recipient.user_permissions.clear()
        permissions = set(self.recipient.get_all_permissions())
        self.client.force_login(self.owner)
        response = self.client.post(
            self.access_url("add_editor"), {"user": self.recipient.username}
        )
        warnings = [
            str(message)
            for message in get_messages(response.wsgi_request)
            if message.level == message_levels.WARNING
        ]
        self.assertTrue(
            any("permission to edit records of this type" in text for text in warnings)
        )
        self.assertEqual(
            set(User.objects.get(pk=self.recipient.pk).get_all_permissions()),
            permissions,
        )
        self.client.force_login(self.recipient)
        response = self.client.get(self.access_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not have permission to edit")

    def test_group_warning_does_not_assign_membership_or_capabilities(self):
        memberships = set(self.team.user_set.values_list("pk", flat=True))
        permissions = set(self.team.permissions.values_list("pk", flat=True))
        self.client.force_login(self.owner)
        response = self.client.post(
            self.access_url("add_editor_group"), {"group": self.team.name}
        )
        warnings = [
            str(message)
            for message in get_messages(response.wsgi_request)
            if message.level == message_levels.WARNING
        ]
        self.assertTrue(any("member's own permissions" in text for text in warnings))
        self.assertEqual(
            set(self.team.user_set.values_list("pk", flat=True)), memberships
        )
        self.assertEqual(
            set(self.team.permissions.values_list("pk", flat=True)), permissions
        )

    def test_frozen_grants_explain_lifecycle_without_changing_state(self):
        self.client.force_login(self.owner)
        for status in ("published", "archived"):
            with self.subTest(status=status):
                self.method.publication_status = status
                self.method.save(update_fields=["publication_status"])
                response = self.client.post(
                    self.access_url("add_editor"), {"user": self.recipient.username}
                )
                warnings = [
                    str(message)
                    for message in get_messages(response.wsgi_request)
                    if message.level == message_levels.WARNING
                ]
                self.assertTrue(any("lifecycle state" in text for text in warnings))
                self.client.force_login(self.recipient)
                self.assertContains(
                    self.client.get(self.access_url()), "lifecycle state"
                )
                self.client.force_login(self.owner)
                self.method.refresh_from_db()
                self.assertEqual(self.method.publication_status, status)
                self.assertEqual(self.method.content_revision, 1)

    def test_private_unrelated_routes_and_spoofed_identity_stay_hidden(self):
        self.method.add_editor(self.recipient, granted_by=self.owner)
        self.method.add_editor(self.other, granted_by=self.owner)
        self.method.add_editor_group(self.team, granted_by=self.owner)
        self.client.force_login(self.recipient)
        response = self.client.get(
            self.access_url() + f"?user={self.other.username}&group={self.team.name}"
        )
        self.assertContains(response, "direct edit grant")
        self.assertNotContains(response, self.other.username)
        self.assertNotContains(response, self.team.name)
        self.assertNotContains(response, "<form")

    def test_existing_unsupported_content_type_is_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "object_management:your_access_modal",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(User).pk,
                    "object_id": self.owner.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_moderator_route_ends_when_owner_withdraws(self):
        moderator = User.objects.create_user(username="access-only-moderator")
        moderator.groups.clear()
        moderator.user_permissions.add(
            Permission.objects.get(
                content_type=self.method_ct,
                codename="can_moderate_analyticalmethod",
            )
        )
        self.method.publication_status = "review"
        self.method.save(update_fields=["publication_status"])
        self.client.force_login(moderator)
        self.assertContains(self.client.get(self.access_url()), "moderator")
        perform_transition(self.owner, self.method, "withdraw")
        response = self.client.get(self.access_url())
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"Shared method", response.content)

    def test_staff_and_inactive_have_no_private_access_route(self):
        for user, status in ((self.staff, 403), (self.inactive, 302)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.access_url())
                self.assertEqual(response.status_code, status)
                self.assertNotIn(b"Shared method", response.content)


class ReviewActivityAccessTests(SharingFixture):
    """In-review shared records expose Review activity to granted editors
    — but pure public readers see no private review links."""

    def test_direct_editor_sees_review_activity(self):
        self.method.publication_status = "review"
        self.method.save()
        ObjectEditorGrant.objects.create(
            content_object=self.method,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse("analyticalmethod-detail", kwargs={"pk": self.method.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review activity")
        listing = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=shared", follow=True
        )
        self.assertContains(listing, self.access_url())
        self.assertContains(listing, "Review activity")
        self.assertNotContains(listing, self.access_url("manage_access_modal"))

    def test_group_editor_sees_review_activity_in_both_detail_layouts(self):
        self.team.user_set.add(self.recipient)
        source = Source.objects.create(
            owner=self.owner, title="Shared source", publication_status="review"
        )
        for obj in (self.method, source):
            obj.publication_status = "review"
            obj.save(update_fields=["publication_status"])
            obj.add_editor_group(self.team, granted_by=self.owner)
        self.client.force_login(self.recipient)
        for obj in (self.method, source):
            with self.subTest(model=type(obj)):
                response = self.client.get(obj.get_absolute_url())
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Review activity")

    def test_pure_published_reader_sees_no_review_links(self):
        self.method.publication_status = "published"
        self.method.save()
        self.other.groups.clear()
        self.other.user_permissions.clear()
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("analyticalmethod-detail", kwargs={"pk": self.method.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review activity")
        self.assertNotContains(response, "Manage access")
        self.assertContains(response, "Your access")


class PrivateListScopeBackendTests(SharingFixture):
    """Plain PrivateObjectListView subclasses must honor ?scope= — the
    workspace nav must not show all-records under every tab."""

    def setUp(self):
        super().setUp()
        self.own_unit = Unit.objects.create(owner=self.recipient, name="own-unit")
        self.shared_unit = Unit.objects.create(owner=self.owner, name="shared-unit")
        ObjectEditorGrant.objects.create(
            content_object=self.shared_unit,
            editor=self.recipient,
            granted_by=self.owner,
        )
        self.foreign_unit = Unit.objects.create(owner=self.other, name="foreign-unit")
        self.public_unit = Unit.objects.create(
            owner=self.other, name="public-unit", publication_status="published"
        )

    def _ids(self, scope):
        response = self.client.get(
            reverse("unit-list-owned") + f"?scope={scope}", follow=True
        )
        self.assertEqual(response.status_code, 200)
        object_list = (
            response.context.get("object_list")
            or response.context.get("page_obj").object_list
        )
        return sorted(obj.pk for obj in object_list)

    def test_scope_private_shows_workspace_only(self):
        self.client.force_login(self.recipient)
        self.assertEqual(
            self._ids("private"),
            sorted([self.own_unit.pk, self.shared_unit.pk]),
        )

    def test_scope_owned_and_shared_partition(self):
        self.client.force_login(self.recipient)
        self.assertEqual(self._ids("owned"), [self.own_unit.pk])
        self.assertEqual(self._ids("shared"), [self.shared_unit.pk])

    def test_scope_unknown_fails_closed(self):
        self.client.force_login(self.recipient)
        for scope in ("bogus", ""):
            with self.subTest(scope=scope):
                self.assertEqual(self._ids(scope), [])

    def test_generic_footer_uses_capability_not_staff_flag(self):
        create_url = Unit.create_url()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("unit-list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{create_url}"')
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("unit-list-owned"))
        self.assertContains(response, f'href="{create_url}"')
