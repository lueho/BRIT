"""Request and persistence regressions for the admin authorization boundary."""

from contextlib import contextmanager
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urljoin

from django import forms
from django.contrib import admin
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Author, Licence, Source, SourceAuthor
from distributions.models import TemporalDistribution, Timestep
from inventories.models import ScenarioInventoryConfiguration
from materials.models import (
    Composition,
    Material,
    MaterialComponentGroup,
    Sample,
    SampleAuthor,
)
from sources.greenhouses.models import (
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
)
from utils.object_management.admin import (
    PolicyAdminMixin,
    PolicyOwnedInlineMixin,
    _active_admin_actor,
    _scope_relation_formfield,
)
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.services import content_mutation, perform_transition
from utils.object_management.tests.test_admin_persistence import _FormCollector
from utils.tests.testcases import ensure_test_default_owner


class AdminSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO(), stderr=StringIO())

    def setUp(self):
        self.actor = User.objects.create_user(username="safe-owner", is_staff=True)
        self.other = User.objects.create_user(username="safe-other", is_staff=True)
        self.source = Source.objects.create(
            owner=self.actor, title="Unchanged", type="misc", citation_key="stable"
        )
        self.source_admin = admin.site._registry[Source]
        self.ct = ContentType.objects.get_for_model(Source)

    def url(self, model, action, obj=None):
        return reverse(
            f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}",
            args=[obj.pk] if obj is not None else [],
        )

    def source_post(self, **changes):
        data = {
            "title": self.source.title,
            "type": "misc",
            "citation_key": self.source.citation_key,
            "sourceauthors-TOTAL_FORMS": "0",
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        data.update(changes)
        return data

    def assert_source_unchanged(self):
        self.source.refresh_from_db()
        self.assertEqual(self.source.title, "Unchanged")
        self.assertEqual(self.source.owner_id, self.actor.pk)
        self.assertEqual(self.source.publication_status, "private")
        self.assertEqual(self.source.content_revision, 1)
        self.assertFalse(self.source.sourceauthors.exists())
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=self.ct, object_id=self.source.pk
            ).exists()
        )

    def test_site_gate_uses_fresh_actor(self):
        request = RequestFactory().post("/admin/")
        request.user = self.actor
        User.objects.filter(pk=self.actor.pk).update(is_staff=False)
        with self.assertRaisesMessage(PermissionDenied, "staff_required"):
            _active_admin_actor(request, admin.site)

    def test_get_cannot_execute_delete_action(self):
        request = RequestFactory().get("/admin/", {"post": "yes"})
        request.user = self.actor
        with (
            patch.object(self.source_admin, "message_user"),
            self.assertRaises(PermissionDenied),
        ):
            self.source_admin.policy_delete_selected(
                request, Source.objects.filter(pk=self.source.pk)
            )
        self.assert_source_unchanged()
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_single_delete_has_exactly_one_log_with_original_id(self):
        self.client.force_login(self.actor)
        pk = self.source.pk
        url = self.url(Source, "delete", self.source)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Source.objects.filter(pk=pk).exists())
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(pk=pk).exists())
        self.assertEqual(
            LogEntry.objects.filter(
                content_type=self.ct, object_id=str(pk), action_flag=DELETION
            ).count(),
            1,
        )
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.ct, object_id=pk, action="deleted"
            ).count(),
            1,
        )

    def test_bulk_delete_rechecks_site_after_root_lock(self):
        request = RequestFactory().post("/admin/", {"post": "yes"})
        request.user = self.actor

        @contextmanager
        def revoke_after_lock(*args, **kwargs):
            with content_mutation(*args, **kwargs) as locked:
                User.objects.filter(pk=self.actor.pk).update(is_staff=False)
                yield locked

        with (
            patch("utils.object_management.admin.content_mutation", revoke_after_lock),
            self.assertRaises(PermissionDenied),
        ):
            self.source_admin._policy_delete_one(request, self.source)
        self.assert_source_unchanged()
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_concurrently_missing_bulk_row_does_not_mask_exception(self):
        self.client.force_login(self.actor)
        gone_pk = self.source.pk
        remaining = Source.objects.create(owner=self.actor, title="Second", type="misc")
        remaining_pk = remaining.pk
        original = self.source_admin._policy_delete_one

        def delete_or_disappear(request, obj, **kwargs):
            if obj.pk == gone_pk:
                Source.objects.get(pk=gone_pk).delete()
                raise Source.DoesNotExist()
            return original(request, obj, **kwargs)

        with patch.object(self.source_admin, "_policy_delete_one", delete_or_disappear):
            response = self.client.post(
                self.url(Source, "changelist"),
                {
                    "action": "delete_selected",
                    "_selected_action": [gone_pk, remaining_pk],
                    "post": "yes",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(pk__in=[gone_pk, remaining_pk]).exists())
        self.assertEqual(
            LogEntry.objects.filter(content_type=self.ct, action_flag=DELETION)
            .values_list("object_id", flat=True)
            .get(),
            str(remaining_pk),
        )

    def test_revoked_capability_after_validation_rolls_back_everything(self):
        self.client.force_login(self.actor)
        original = admin.ModelAdmin.save_form
        calls = []

        def revoke_after_validation(model_admin, request, form, change):
            obj = original(model_admin, request, form, change)
            self.assertTrue(request.user.has_perm("bibliography.change_source"))
            calls.append(obj.pk)
            request.user.groups.clear()
            return obj

        with (
            patch.object(admin.ModelAdmin, "save_form", revoke_after_validation),
            self.assertLogs("django.request", level="WARNING") as logged,
        ):
            response = self.client.post(
                self.url(Source, "change", self.source),
                self.source_post(title="Must not persist"),
            )
        self.assertEqual(calls, [self.source.pk])
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", "\n".join(logged.output))
        self.assert_source_unchanged()

    def test_owned_inline_wrong_fk_cannot_write_through_author_admin(self):
        class WrongInline(PolicyOwnedInlineMixin, admin.TabularInline):
            model = SourceAuthor
            fk_name = "author"
            fields = ("position",)

        author = Author.objects.create(
            owner=self.actor, first_names="Original", last_names="Author"
        )
        foreign_source = Source.objects.create(
            owner=self.other, title="Published", publication_status="published"
        )
        child = SourceAuthor.objects.create(
            source=foreign_source, author=author, position=1
        )
        self.client.force_login(self.actor)
        author_admin = admin.site._registry[Author]
        with (
            patch.object(type(author_admin), "inlines", [WrongInline]),
            patch.object(WrongInline, "has_add_permission", return_value=True),
            patch.object(WrongInline, "has_change_permission", return_value=True),
            patch.object(WrongInline, "has_delete_permission", return_value=True),
            self.assertLogs("django.request", level="WARNING"),
        ):
            response = self.client.post(
                self.url(Author, "change", author),
                {
                    "author_type": "person",
                    "first_names": "Must roll back",
                    "last_names": "Author",
                    "sourceauthors-TOTAL_FORMS": "1",
                    "sourceauthors-INITIAL_FORMS": "1",
                    "sourceauthors-0-id": child.pk,
                    "sourceauthors-0-author": author.pk,
                    "sourceauthors-0-position": "9",
                    "_save": "Save",
                },
            )
        self.assertEqual(response.status_code, 403)
        author.refresh_from_db()
        child.refresh_from_db()
        foreign_source.refresh_from_db()
        self.assertEqual(author.first_names, "Original")
        self.assertEqual(author.content_revision, 1)
        self.assertEqual(child.position, 1)
        self.assertEqual(child.source_id, foreign_source.pk)
        self.assertEqual(foreign_source.content_revision, 1)
        self.assertFalse(ReviewAction.objects.exists())

    def test_registered_non_uco_relation_uses_visibility_scope(self):
        field = forms.ModelChoiceField(
            queryset=ScenarioInventoryConfiguration.objects.all()
        )
        original_queryset = field.queryset
        db_field = SimpleNamespace(
            remote_field=SimpleNamespace(model=ScenarioInventoryConfiguration)
        )
        with patch(
            "utils.object_management.admin.visible_queryset",
            return_value=ScenarioInventoryConfiguration.objects.none(),
        ) as scoped:
            _scope_relation_formfield(field, db_field, self.actor)
        scoped.assert_called_once_with(self.actor, original_queryset)
        self.assertFalse(field.queryset.exists())

    def test_multihop_owned_inline_add_uses_root_context(self):
        class ShareInline(PolicyOwnedInlineMixin, admin.TabularInline):
            model = GrowthShare
            fk_name = "timestepset"

        greenhouse = Greenhouse.objects.create(owner=self.actor)
        cycle = GreenhouseGrowthCycle.objects.create(
            owner=self.actor, greenhouse=greenhouse
        )
        distribution = TemporalDistribution.objects.create(
            owner=self.actor, name="Reference"
        )
        timestep = Timestep.objects.create(
            owner=self.actor, name="January", order=1, distribution=distribution
        )
        parent = GrowthTimeStepSet.objects.create(
            owner=self.actor, growth_cycle=cycle, timestep=timestep
        )
        inline = ShareInline(GrowthTimeStepSet, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        self.assertFalse(self.actor.has_perm("greenhouses.add_growthshare"))
        self.assertTrue(inline.has_add_permission(request, parent))

    def test_create_rechecks_cached_admin_before_writing_inline_reference(self):
        author = Author.objects.create(
            owner=self.other, first_names="Private", last_names="Author"
        )
        permission = Permission.objects.get(codename="administer_objects")
        self.actor.user_permissions.add(permission)
        self.client.force_login(self.actor)
        original = admin.ModelAdmin.save_model
        saved = []

        def revoke_after_scalar_save(model_admin, request, obj, form, change):
            original(model_admin, request, obj, form, change)
            self.assertTrue(
                request.user.has_perm("object_management.administer_objects")
            )
            saved.append(obj.pk)
            request.user.user_permissions.remove(permission)

        with (
            patch.object(admin.ModelAdmin, "save_model", revoke_after_scalar_save),
            self.assertLogs("django.request", level="WARNING"),
        ):
            response = self.client.post(
                self.url(Source, "add"),
                self.source_post(
                    title="Must not be created",
                    citation_key="forbidden-new",
                    **{
                        "sourceauthors-TOTAL_FORMS": "1",
                        "sourceauthors-0-author": author.pk,
                        "sourceauthors-0-position": "1",
                    },
                ),
            )
        self.assertEqual(len(saved), 1)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Source.objects.filter(pk=saved[0]).exists())
        self.assertFalse(SourceAuthor.objects.filter(author=author).exists())
        self.assert_source_unchanged()

    def test_owned_creation_rechecks_staff_after_acquiring_parent_boundary(self):
        material = Material.objects.create(owner=self.actor, name="Material")
        sample = Sample.objects.create(
            owner=self.actor, name="Sample", material=material
        )
        group = MaterialComponentGroup.objects.create(
            owner=self.actor, name="Composition group"
        )
        before_children = list(Composition.objects.filter(sample=sample).values())
        self.client.force_login(self.actor)
        original = PolicyAdminMixin._open_owned_save_boundary
        calls = []

        def revoke_after_boundary(model_admin, request, parent):
            locked = original(model_admin, request, parent)
            calls.append(locked.pk)
            User.objects.filter(pk=self.actor.pk).update(is_staff=False)
            return locked

        with (
            patch.object(
                PolicyAdminMixin, "_open_owned_save_boundary", revoke_after_boundary
            ),
            self.assertLogs("django.request", level="WARNING"),
        ):
            response = self.client.post(
                self.url(Composition, "add"),
                {
                    "name": "Must not be created",
                    "sample": sample.pk,
                    "group": group.pk,
                    "order": "1",
                    "_save": "Save",
                },
            )
        self.assertEqual(calls, [sample.pk])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            list(Composition.objects.filter(sample=sample).values()), before_children
        )
        sample.refresh_from_db()
        self.assertEqual(sample.content_revision, 1)
        self.assertFalse(ReviewAction.objects.exists())

    def confirmation(self, model, objects):
        url = self.url(model, "changelist")
        response = self.client.post(
            url,
            {
                "action": "delete_selected",
                "_selected_action": [obj.pk for obj in objects],
            },
        )
        self.assertEqual(response.status_code, 200)
        parser = _FormCollector()
        parser.feed(response.content.decode())
        self.assertEqual(parser.hidden["action"], ["delete_selected"])
        return response, urljoin(url, parser.action), parser.hidden

    def test_bulk_confirmation_preserves_multiple_ids_and_nested_preview(self):
        second = Source.objects.create(owner=self.actor, title="Second", type="misc")
        self.client.force_login(self.actor)
        response, target, data = self.confirmation(Source, [self.source, second])
        self.assertIsInstance(response.context["deletable_objects"][0], list)
        ids = sorted([str(self.source.pk), str(second.pk)])
        self.assertEqual(sorted(data["_selected_action"]), ids)
        self.assertTrue(Source.objects.filter(pk=self.source.pk).exists())
        self.assertTrue(Source.objects.filter(pk=second.pk).exists())
        self.assertFalse(ReviewAction.objects.exists())
        self.assertEqual(data["post"], ["yes"])
        response = self.client.post(target, data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(pk__in=ids).exists())
        self.assertCountEqual(
            LogEntry.objects.filter(
                content_type=self.ct, action_flag=DELETION
            ).values_list("object_id", flat=True),
            ids,
        )

    def test_confirmation_rechecks_revoked_delete_permission(self):
        self.client.force_login(self.actor)
        _, target, data = self.confirmation(Source, [self.source])
        self.actor.groups.clear()
        self.assertFalse(
            User.objects.get(pk=self.actor.pk).has_perm("bibliography.delete_source")
        )
        response = self.client.post(target, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 record(s) skipped")
        self.assert_source_unchanged()
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_confirmation_rechecks_record_moved_to_review(self):
        self.client.force_login(self.actor)
        _, target, data = self.confirmation(Source, [self.source])
        Source.objects.filter(pk=self.source.pk).update(publication_status="review")
        response = self.client.post(target, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 record(s) skipped")
        self.source.refresh_from_db()
        self.assertEqual(self.source.publication_status, "review")
        self.assertEqual(self.source.content_revision, 1)
        self.assertFalse(ReviewAction.objects.exists())
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_bulk_audit_failure_rolls_back_root_and_django_log(self):
        self.client.force_login(self.actor)
        self.client.raise_request_exception = False
        with (
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("delete audit unavailable"),
            ),
            self.assertLogs("django.request", level="ERROR") as logged,
        ):
            response = self.client.post(
                self.url(Source, "changelist"),
                {
                    "action": "delete_selected",
                    "_selected_action": [self.source.pk],
                    "post": "yes",
                },
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("delete audit unavailable", "\n".join(logged.output))
        self.assert_source_unchanged()
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_protected_delete_preview_is_generic_forbidden_not_server_error(self):
        licence = Licence.objects.create(owner=self.actor, name="Protected licence")
        foreign_source = Source.objects.create(
            owner=self.other, title="Unreadable protected source", licence=licence
        )
        self.client.force_login(self.actor)
        self.client.raise_request_exception = False
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(self.url(Licence, "delete", licence))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Unreadable protected source", response.content.decode())
        self.assertTrue(Licence.objects.filter(pk=licence.pk).exists())
        foreign_source.refresh_from_db()
        self.assertEqual(foreign_source.licence_id, licence.pk)
        self.assertEqual(foreign_source.content_revision, 1)
        self.assertFalse(ReviewAction.objects.exists())

    def test_bulk_preview_hides_private_leaf_and_keeps_blocked_root(self):
        blocked = Author.objects.create(
            owner=self.actor, first_names="Blocked", last_names="Author"
        )
        allowed = Author.objects.create(
            owner=self.actor, first_names="Allowed", last_names="Author"
        )
        foreign_source = Source.objects.create(
            owner=self.other, title="Unreadable parent"
        )
        child = SourceAuthor.objects.create(
            source=foreign_source, author=blocked, position=73891
        )
        self.client.force_login(self.actor)
        response, target, data = self.confirmation(Author, [blocked, allowed])
        self.assertNotContains(response, "73891")
        self.assertNotContains(response, "Unreadable parent")
        self.assertEqual(data["_selected_action"], [str(allowed.pk)])
        response = self.client.post(target, data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Author.objects.filter(pk=allowed.pk).exists())
        blocked.refresh_from_db()
        child.refresh_from_db()
        foreign_source.refresh_from_db()
        self.assertEqual(blocked.content_revision, 1)
        self.assertEqual(child.position, 73891)
        self.assertEqual(foreign_source.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Author),
                object_id=blocked.pk,
            ).exists()
        )

    def test_foreign_inline_identity_cannot_be_changed_or_deleted(self):
        author = Author.objects.create(
            owner=self.actor, first_names="Visible", last_names="Author"
        )
        foreign = Source.objects.create(
            owner=self.other, title="Foreign parent", publication_status="published"
        )
        child = SourceAuthor.objects.create(source=foreign, author=author, position=1)
        self.client.force_login(self.actor)
        for delete in (False, True):
            with self.subTest(delete=delete):
                payload = self.source_post(
                    title="Must not change",
                    **{
                        "sourceauthors-TOTAL_FORMS": "1",
                        "sourceauthors-INITIAL_FORMS": "1",
                        "sourceauthors-0-id": child.pk,
                        "sourceauthors-0-author": author.pk,
                        "sourceauthors-0-position": "2",
                    },
                )
                if delete:
                    payload["sourceauthors-0-DELETE"] = "on"
                with self.assertLogs("django.request", level="WARNING"):
                    response = self.client.post(
                        self.url(Source, "change", self.source), payload
                    )
                self.assertEqual(response.status_code, 403)
                self.assert_source_unchanged()
                child.refresh_from_db()
                foreign.refresh_from_db()
                self.assertEqual(child.source_id, foreign.pk)
                self.assertEqual(child.position, 1)
                self.assertEqual(foreign.content_revision, 1)
                self.assertEqual(foreign.publication_status, "published")

    def test_add_only_source_creator_needs_no_author_or_child_capability(self):
        self.actor.groups.clear()
        self.actor.user_permissions.add(
            Permission.objects.get(content_type=self.ct, codename="add_source")
        )
        actor = User.objects.get(pk=self.actor.pk)
        for permission in (
            "bibliography.change_source",
            "bibliography.add_author",
            "bibliography.add_sourceauthor",
            "bibliography.change_sourceauthor",
            "bibliography.delete_sourceauthor",
        ):
            self.assertFalse(actor.has_perm(permission), permission)
        author = Author.objects.create(
            owner=self.other,
            first_names="Existing",
            last_names="Author",
            publication_status="published",
        )
        self.client.force_login(actor)
        response = self.client.post(
            self.url(Source, "add"),
            self.source_post(
                title="Add only",
                citation_key="add-only",
                **{
                    "sourceauthors-TOTAL_FORMS": "1",
                    "sourceauthors-0-author": author.pk,
                    "sourceauthors-0-position": "1",
                },
            ),
        )
        self.assertEqual(response.status_code, 302)
        created = Source.objects.get(citation_key="add-only")
        self.assertEqual(created.owner_id, actor.pk)
        self.assertEqual(created.publication_status, "private")
        self.assertEqual(created.content_revision, 1)
        self.assertEqual(created.sourceauthors.get().position, 1)
        self.assertEqual(
            ReviewAction.objects.filter(content_type=self.ct, object_id=created.pk)
            .values_list("action", flat=True)
            .get(),
            "created",
        )

    def test_direct_and_group_editors_change_and_delete_owned_rows_in_review(self):
        author = Author.objects.create(
            owner=self.actor,
            first_names="Visible",
            last_names="Author",
            publication_status="published",
        )
        for route in ("direct", "group"):
            with self.subTest(route=route):
                source = Source.objects.create(
                    owner=self.actor,
                    title=route,
                    type="misc",
                    citation_key=route,
                    publication_status="review",
                )
                if route == "direct":
                    source.add_editor(self.other, granted_by=self.actor)
                else:
                    team = Group.objects.create(name="Source editors")
                    self.other.groups.add(team)
                    source.add_editor_group(team, granted_by=self.actor)
                for verb in ("add", "change", "delete"):
                    self.assertFalse(
                        User.objects.get(pk=self.other.pk).has_perm(
                            f"bibliography.{verb}_sourceauthor"
                        )
                    )
                self.client.force_login(self.other)
                payload = self.source_post(
                    title="Edited in review",
                    citation_key=route,
                    **{
                        "sourceauthors-TOTAL_FORMS": "1",
                        "sourceauthors-0-author": author.pk,
                        "sourceauthors-0-position": "1",
                    },
                )
                response = self.client.post(self.url(Source, "change", source), payload)
                self.assertEqual(response.status_code, 302)
                source.refresh_from_db()
                self.assertEqual(source.publication_status, "review")
                self.assertEqual(source.content_revision, 2)
                child = source.sourceauthors.get()
                payload.update(
                    {
                        "sourceauthors-INITIAL_FORMS": "1",
                        "sourceauthors-0-id": child.pk,
                        "sourceauthors-0-position": "2",
                    }
                )
                response = self.client.post(self.url(Source, "change", source), payload)
                self.assertEqual(response.status_code, 302)
                child.refresh_from_db()
                self.assertEqual(child.position, 2)
                payload["sourceauthors-0-DELETE"] = "on"
                response = self.client.post(self.url(Source, "change", source), payload)
                self.assertEqual(response.status_code, 302)
                source.refresh_from_db()
                self.assertEqual(source.content_revision, 4)
                self.assertFalse(source.sourceauthors.exists())
                self.assertEqual(
                    ReviewAction.objects.filter(
                        content_type=self.ct, object_id=source.pk, action="edited"
                    ).count(),
                    3,
                )
                if route == "direct":
                    source.remove_editor(self.other)
                else:
                    self.other.groups.remove(team)
                payload["title"] = "Revoked edit"
                response = self.client.post(self.url(Source, "change", source), payload)
                self.assertEqual(response.status_code, 302)
                source.refresh_from_db()
                self.assertEqual(source.title, "Edited in review")
                self.assertEqual(source.content_revision, 4)

    def test_editor_grant_without_model_capability_cannot_edit(self):
        self.source.add_editor(self.other, granted_by=self.actor)
        self.other.groups.clear()
        self.other.user_permissions.clear()
        self.client.force_login(self.other)
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.post(
                self.url(Source, "change", self.source),
                self.source_post(title="Grant is not a capability"),
            )
        self.assertEqual(response.status_code, 403)
        self.assert_source_unchanged()

    def test_noop_after_valid_compound_creation_has_no_extra_revision_or_audit(self):
        self.client.force_login(self.actor)
        author = Author.objects.create(
            owner=self.actor, first_names="Existing", last_names="Author"
        )
        payload = self.source_post(
            title="No op",
            citation_key="no-op",
            **{
                "sourceauthors-TOTAL_FORMS": "1",
                "sourceauthors-0-author": author.pk,
                "sourceauthors-0-position": "1",
            },
        )
        response = self.client.post(self.url(Source, "add"), payload)
        self.assertEqual(response.status_code, 302)
        created = Source.objects.get(citation_key="no-op")
        payload.update(
            {
                "sourceauthors-INITIAL_FORMS": "1",
                "sourceauthors-0-id": created.sourceauthors.get().pk,
            }
        )
        response = self.client.post(self.url(Source, "change", created), payload)
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.content_revision, 1)
        self.assertEqual(
            ReviewAction.objects.filter(content_type=self.ct, object_id=created.pk)
            .values_list("action", flat=True)
            .get(),
            "created",
        )

    def test_explicit_non_superuser_administrator_reads_orphan_and_owned_audit(self):
        self.actor.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.assertFalse(self.actor.is_superuser)
        author = Author.objects.create(
            owner=self.actor, first_names="Existing", last_names="Author"
        )
        child = SourceAuthor.objects.create(
            source=self.source, author=author, position=1
        )
        events = [
            ReviewAction.objects.create(
                content_type=self.ct,
                object_id=self.source.pk + 1000000,
                action="deleted",
                user=self.actor,
            ),
            ReviewAction.objects.create(
                content_type=ContentType.objects.get_for_model(SourceAuthor),
                object_id=child.pk,
                action="edited",
                user=self.actor,
            ),
        ]
        self.client.force_login(self.actor)
        response = self.client.get(self.url(ReviewAction, "changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context["cl"].result_list, events)
        for event in events:
            response = self.client.get(self.url(ReviewAction, "change", event))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'name="_save"')

    def test_superuser_cannot_add_change_delete_or_bulk_delete_audit(self):
        user = User.objects.create_superuser(
            username="audit-superuser", email="audit@example.test", password=None
        )
        event = ReviewAction.objects.create(
            content_type=self.ct,
            object_id=self.source.pk,
            action="commented",
            comment="Keep this history",
            user=self.actor,
        )
        self.client.force_login(user)
        for action in ("add", "change", "delete"):
            with self.subTest(action=action):
                with self.assertLogs("django.request", level="WARNING"):
                    response = self.client.post(
                        self.url(
                            ReviewAction, action, event if action != "add" else None
                        ),
                        {"action": "deleted", "post": "yes", "_save": "Save"},
                    )
                self.assertEqual(response.status_code, 403)
        response = self.client.post(
            self.url(ReviewAction, "changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [event.pk],
                "post": "yes",
            },
        )
        # With no permitted actions Django simply renders the changelist.
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="delete_selected"')
        event.refresh_from_db()
        self.assertEqual(event.comment, "Keep this history")
        self.assertEqual(event.action, "commented")
        self.assertEqual(ReviewAction.objects.count(), 1)

    def test_group_activity_access_and_moderator_withdrawal_visibility(self):
        Source.objects.filter(pk=self.source.pk).update(publication_status="review")
        self.source.refresh_from_db()
        event = ReviewAction.objects.create(
            content_type=self.ct,
            object_id=self.source.pk,
            action="commented",
            comment="Retain the review conversation",
            user=self.actor,
        )
        group = Group.objects.create(name="Review participants")
        self.other.groups.add(group)
        self.source.add_editor_group(group, granted_by=self.actor)
        self.client.force_login(self.other)
        response = self.client.get(self.url(ReviewAction, "change", event))
        self.assertEqual(response.status_code, 200)
        self.source.remove_editor_group(group)
        moderator = User.objects.create_user(username="audit-moderator", is_staff=True)
        moderator.user_permissions.add(
            Permission.objects.get(content_type=self.ct, codename="can_moderate_source")
        )
        self.client.force_login(moderator)
        response = self.client.get(self.url(ReviewAction, "changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(event, response.context["cl"].result_list)
        perform_transition(self.actor, self.source, "withdraw")
        response = self.client.get(self.url(ReviewAction, "changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(event, response.context["cl"].result_list)
        self.other.groups.clear()
        self.other.user_permissions.add(
            Permission.objects.get(codename="view_reviewaction")
        )
        self.client.force_login(self.other)
        response = self.client.get(self.url(ReviewAction, "changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(event, response.context["cl"].result_list)
        self.client.force_login(self.actor)
        response = self.client.get(self.url(ReviewAction, "changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(event, response.context["cl"].result_list)
        event.refresh_from_db()
        self.assertEqual(event.comment, "Retain the review conversation")

    def test_bulk_preview_filters_lifecycle_and_foreign_editor_deletions(self):
        eligible = [self.source]
        eligible.append(
            Source.objects.create(
                owner=self.actor, title="Declined", publication_status="declined"
            )
        )
        blocked = [
            Source.objects.create(
                owner=self.actor, title=state, publication_status=state
            )
            for state in ("review", "published", "archived")
        ]
        shared = Source.objects.create(owner=self.other, title="Shared private")
        shared.add_editor(self.actor, granted_by=self.other)
        blocked.append(shared)
        self.client.force_login(self.actor)
        response, target, data = self.confirmation(Source, eligible + blocked)
        self.assertContains(response, "4 record(s) skipped")
        self.assertCountEqual(
            data["_selected_action"], [str(obj.pk) for obj in eligible]
        )
        response = self.client.post(target, data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Source.objects.filter(pk__in=[obj.pk for obj in eligible]).exists()
        )
        for obj in blocked:
            obj.refresh_from_db()
            self.assertEqual(obj.content_revision, 1)
            self.assertFalse(
                ReviewAction.objects.filter(
                    content_type=self.ct, object_id=obj.pk
                ).exists()
            )


class SampleAuthorInlinePolicyTests(TestCase):
    """Owned-child inline authorization on ``Sample.sample_authors``.

    The actor edits a FOREIGN private ``Sample`` through an object-level
    editor grant — never ownership — while ``SampleAuthor`` is a registered
    owned child (``materials.sampleauthor`` → ``sample``). Every inline write
    must delegate to the parent's edit decision and author references must be
    readable rows; legacy child-model CRUD permissions must not reopen a
    write path on their own.
    """

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO(), stderr=StringIO())

    def setUp(self):
        self.actor = User.objects.create_user(username="sa-actor", is_staff=True)
        self.other = User.objects.create_user(username="sa-owner", is_staff=True)
        self.material = Material.objects.create(
            owner=self.other,
            name="SA Material",
            publication_status="published",
        )
        self.sample = Sample.objects.create(
            owner=self.other,
            name="SA Sample",
            material=self.material,
            standalone=True,
            publication_status="private",
        )
        # Sample.sources is a required (blank=False) M2M; give the sample one
        # readable published source so scalar validation is clean.
        self.source = Source.objects.create(
            owner=self.other,
            title="SA Source",
            type="misc",
            publication_status="published",
        )
        self.sample.sources.add(self.source)
        self.sample.add_editor(self.actor, granted_by=self.other)
        self.own_author = Author.objects.create(
            owner=self.actor,
            first_names="Own",
            last_names="Author",
            publication_status="private",
        )
        self.public_author = Author.objects.create(
            owner=self.other,
            first_names="Public",
            last_names="Author",
            publication_status="published",
        )
        self.shared_author = Author.objects.create(
            owner=self.other,
            first_names="Shared",
            last_names="Author",
            publication_status="private",
        )
        self.shared_author.add_editor(self.actor, granted_by=self.other)
        self.foreign_private_author = Author.objects.create(
            owner=self.other,
            first_names="Foreign",
            last_names="Private",
            publication_status="private",
        )
        self.ct = ContentType.objects.get_for_model(Sample)
        self.change_url = reverse(
            "admin:materials_sample_change", args=[self.sample.pk]
        )
        self.client.force_login(self.actor)

    def _grant_child_perm(self, codename):
        self.actor.user_permissions.add(
            Permission.objects.get(
                codename=codename,
                content_type=ContentType.objects.get_for_model(SampleAuthor),
            )
        )

    def _sample_post(self, rows, *, name=None):
        data = {
            "name": name if name is not None else self.sample.name,
            "material": self.material.pk,
            "standalone": "on",
            "sources": [self.source.pk],
            "sample_authors-TOTAL_FORMS": str(len(rows)),
            "sample_authors-INITIAL_FORMS": str(sum(1 for row in rows if "id" in row)),
            "sample_authors-MIN_NUM_FORMS": "0",
            "sample_authors-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        for index, row in enumerate(rows):
            for key, value in row.items():
                data[f"sample_authors-{index}-{key}"] = value
        return data

    def _assert_sample_untouched(self, name="SA Sample"):
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.name, name)
        self.assertEqual(self.sample.owner_id, self.other.pk)
        self.assertEqual(self.sample.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=self.ct, object_id=self.sample.pk
            ).exists()
        )
        self.assertFalse(LogEntry.objects.exists())

    def _inline_author_errors(self, response):
        """Return the inline formset's author-field errors, keyed by form index."""
        formset = response.context["inline_admin_formsets"][0].formset
        return {
            index: form.errors["author"]
            for index, form in enumerate(formset.forms)
            if "author" in form.errors
        }

    def test_forged_foreign_private_author_add_rejected(self):
        # Explicit legacy child CRUD proves the pre-policy stock inline would
        # have been writable — this is not a hidden-inline false negative.
        self._grant_child_perm("add_sampleauthor")
        self._grant_child_perm("change_sampleauthor")
        response = self.client.post(
            self.change_url,
            self._sample_post(
                [{"author": self.foreign_private_author.pk, "position": "1"}],
                name="Forged name",
            ),
        )
        self.assertEqual(response.status_code, 200)
        # The scalar Sample form is clean; only the narrowed author field
        # rejects the forged reference.
        self.assertEqual(response.context["adminform"].form.errors, {})
        self.assertIn(0, self._inline_author_errors(response))
        self.assertFalse(
            SampleAuthor.objects.filter(author=self.foreign_private_author).exists()
        )
        self._assert_sample_untouched()

    def test_forged_update_existing_link_rejected(self):
        self._grant_child_perm("change_sampleauthor")
        link = SampleAuthor.objects.create(
            sample=self.sample, author=self.own_author, position=1
        )
        response = self.client.post(
            self.change_url,
            self._sample_post(
                [
                    {
                        "id": link.pk,
                        "author": self.foreign_private_author.pk,
                        "position": "9",
                    }
                ]
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["adminform"].form.errors, {})
        self.assertIn(0, self._inline_author_errors(response))
        link.refresh_from_db()
        self.assertEqual(link.author_id, self.own_author.pk)
        self.assertEqual(link.position, 1)
        self._assert_sample_untouched()

    def test_change_view_author_field_queryset_is_scoped(self):
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 200)
        formset = response.context["inline_admin_formsets"][0].formset
        bound_forms = list(formset.forms) + [formset.empty_form]
        self.assertTrue(bound_forms)
        for form in bound_forms:
            field = form.fields["author"]
            pks = set(field.queryset.values_list("pk", flat=True))
            self.assertNotIn(self.foreign_private_author.pk, pks)
            self.assertIn(self.own_author.pk, pks)
            self.assertIn(self.public_author.pk, pks)
            self.assertIn(self.shared_author.pk, pks)

    def test_allowed_link_add_via_parent_edit_without_child_perms(self):
        # Keep the contributor's Sample capabilities and parent edit grant;
        # owned links do not require separate SampleAuthor CRUD permissions.
        self.assertFalse(self.actor.has_perm("materials.add_sampleauthor"))
        self.assertFalse(self.actor.has_perm("materials.change_sampleauthor"))
        response = self.client.post(
            self.change_url,
            self._sample_post(
                [
                    {"author": self.public_author.pk, "position": "1"},
                    {"author": self.shared_author.pk, "position": "2"},
                ]
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SampleAuthor.objects.filter(sample=self.sample).count(), 2)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.owner_id, self.other.pk)
        self.assertEqual(self.sample.publication_status, "private")
        self.assertEqual(self.sample.name, "SA Sample")
        self.assertEqual(self.sample.content_revision, 2)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.ct,
                object_id=self.sample.pk,
                action=ReviewAction.ACTION_EDITED,
                user=self.actor,
            ).count(),
            1,
        )
        self.public_author.refresh_from_db()
        self.shared_author.refresh_from_db()
        for author in (self.public_author, self.shared_author):
            self.assertEqual(author.owner_id, self.other.pk)
            self.assertEqual(author.content_revision, 1)

    def test_allowed_position_only_update_bumps_root_once(self):
        link = SampleAuthor.objects.create(
            sample=self.sample, author=self.public_author, position=1
        )
        response = self.client.post(
            self.change_url,
            self._sample_post(
                [
                    {
                        "id": link.pk,
                        "author": self.public_author.pk,
                        "position": "7",
                    }
                ]
            ),
        )
        self.assertEqual(response.status_code, 302)
        link.refresh_from_db()
        self.assertEqual(link.author_id, self.public_author.pk)
        self.assertEqual(link.position, 7)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, 2)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.ct, object_id=self.sample.pk
            ).count(),
            1,
        )

    def test_revoked_reference_read_inside_boundary_rolls_back(self):
        # shared_author is readable at form-validation time; revoking the
        # grant inside the root save transaction — after save_model, before
        # save_formset — must deny the persistence-time reference
        # revalidation and roll back every row.
        original_save_model = admin.ModelAdmin.save_model
        seen = []

        def revoke_in_save_model(model_admin, request, obj, form, change):
            original_save_model(model_admin, request, obj, form, change)
            seen.append(obj.pk)
            ObjectEditorGrant.for_object(self.shared_author).delete()

        with (
            patch.object(admin.ModelAdmin, "save_model", revoke_in_save_model),
            self.assertLogs("django.request", level="WARNING") as logged,
        ):
            response = self.client.post(
                self.change_url,
                self._sample_post(
                    [{"author": self.shared_author.pk, "position": "1"}],
                    name="Must roll back",
                ),
            )
        self.assertEqual(seen, [self.sample.pk])
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", "\n".join(logged.output))
        self.assertFalse(SampleAuthor.objects.filter(sample=self.sample).exists())
        self._assert_sample_untouched()

    def test_delete_link_to_inaccessible_author_allowed(self):
        # Removing a link must not require read access on the referenced row.
        link = SampleAuthor.objects.create(
            sample=self.sample,
            author=self.foreign_private_author,
            position=1,
        )
        response = self.client.post(
            self.change_url,
            self._sample_post(
                [
                    {
                        "id": link.pk,
                        "author": self.foreign_private_author.pk,
                        "position": "1",
                        "DELETE": "on",
                    }
                ],
                name="Renamed",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SampleAuthor.objects.filter(pk=link.pk).exists())
        self.assertTrue(
            Author.objects.filter(pk=self.foreign_private_author.pk).exists()
        )
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, 2)

    def test_frozen_published_sample_denies_inline_mutation(self):
        self.sample.publication_status = "published"
        self.sample.save()
        with self.assertLogs("django.request", level="WARNING") as logged:
            response = self.client.post(
                self.change_url,
                self._sample_post([{"author": self.public_author.pk, "position": "1"}]),
            )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", "\n".join(logged.output))
        self.assertFalse(SampleAuthor.objects.filter(sample=self.sample).exists())
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.name, "SA Sample")
        self.assertEqual(self.sample.publication_status, "published")
        self.assertEqual(self.sample.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=self.ct, object_id=self.sample.pk
            ).exists()
        )
        self.assertFalse(LogEntry.objects.exists())
