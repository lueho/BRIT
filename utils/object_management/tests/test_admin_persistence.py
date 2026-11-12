"""Admin persistence boundary regressions: confirmation-gated deletion,
leaf-privacy previews, fresh-actor hooks, owned-inline binding/read."""

from html.parser import HTMLParser
from io import StringIO
from unittest.mock import patch
from urllib.parse import urljoin

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from bibliography.models import Author, Source, SourceAuthor
from utils.object_management.admin import PolicyAdminMixin
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.tests.testcases import ensure_test_default_owner


def _admin_url(model, action, pk=None):
    name = f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}"
    return reverse(name, kwargs={"object_id": pk}) if pk else reverse(name)


class _FormCollector(HTMLParser):
    """Collect hidden inputs from the rendered confirmation form."""

    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.action = ""
        self.current_form = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current_form = {
                "method": attrs.get("method", "get").lower(),
                "action": attrs.get("action", ""),
                "hidden": {},
            }
        if (
            self.current_form is not None
            and tag == "input"
            and attrs.get("type") == "hidden"
        ):
            name = attrs.get("name")
            if name:
                self.current_form["hidden"].setdefault(name, []).append(
                    attrs.get("value", "")
                )

    def handle_endtag(self, tag):
        if tag != "form" or self.current_form is None:
            return
        if self.current_form["method"] == "post" and self.current_form["hidden"].get(
            "action"
        ) == ["delete_selected"]:
            self.hidden = self.current_form["hidden"]
            self.action = self.current_form["action"]
        self.current_form = None


class PersistenceFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO(), stderr=StringIO())

    def setUp(self):
        self.owner = User.objects.create_user(username="p-owner", is_staff=True)
        self.foreign = User.objects.create_user(username="p-foreign", is_staff=True)


class DeleteConfirmationTests(PersistenceFixture):
    """Bulk delete uses the standard action id, previews before deleting,
    and logs real deletions inside their transaction."""

    def test_action_is_registered_as_delete_selected(self):
        Source.objects.create(
            owner=self.owner, title="Visible row", publication_status="private"
        )
        self.client.force_login(self.owner)
        response = self.client.get(_admin_url(Source, "changelist"))
        self.assertEqual(response.status_code, 200)
        # The stock template posts action=delete_selected.
        self.assertContains(response, 'name="action"')
        self.assertContains(response, 'value="delete_selected"')

    def test_initial_post_only_confirms(self):
        source = Source.objects.create(
            owner=self.owner, title="Confirm me", publication_status="private"
        )
        self.client.force_login(self.owner)
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="delete_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )
        response = self.client.post(
            _admin_url(Source, "changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [str(source.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        # Still present: confirmation only.
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())
        self.assertContains(response, 'name="action"')

    def test_confirmed_bulk_delete_removes_and_logs(self):
        source = Source.objects.create(
            owner=self.owner, title="Delete me", publication_status="private"
        )
        self.client.force_login(self.owner)
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="delete_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )
        # Confirm step renders the real form.
        response = self.client.post(
            _admin_url(Source, "changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [str(source.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        collector = _FormCollector()
        collector.feed(response.content.decode())
        self.assertEqual(collector.hidden.get("action"), ["delete_selected"])
        # Second pass: confirm via the real hidden fields.
        data = collector.hidden
        self.assertEqual(data["post"], ["yes"])
        response = self.client.post(
            urljoin(_admin_url(Source, "changelist"), collector.action), data=data
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(pk=source.pk).exists())
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                object_id=source.pk,
                action="deleted",
            ).exists()
        )

    def test_blocked_root_skipped_in_bulk_preview_and_delete(self):
        """Foreign private record silently skipped; eligible one deletes."""
        eligible = Source.objects.create(
            owner=self.owner, title="Mine", publication_status="private"
        )
        foreign = Source.objects.create(
            owner=self.foreign, title="Theirs", publication_status="private"
        )
        self.client.force_login(self.owner)
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="delete_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )
        # visible_queryset already excludes the foreign private row; the
        # preview must not enumerate it.
        response = self.client.post(
            _admin_url(Source, "changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [str(eligible.pk), str(foreign.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Theirs")
        # Confirm deletion.
        collector = _FormCollector()
        collector.feed(response.content.decode())
        data = collector.hidden
        response = self.client.post(
            urljoin(_admin_url(Source, "changelist"), collector.action), data=data
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(pk=eligible.pk).exists())
        self.assertTrue(Source.objects.filter(pk=foreign.pk).exists())


class LeafPrivacyPreviewTests(PersistenceFixture):
    """A private owned-child leaf must not leak through a parent's delete
    preview even when the child model has no standalone ModelAdmin."""

    def test_foreign_private_child_hidden_from_delete_preview(self):
        # Owner A's author; owner B's private Source references it.
        author_a = Author.objects.create(
            owner=self.owner,
            first_names="Ada",
            last_names="Lovelace",
            publication_status="private",
        )
        foreign_source = Source.objects.create(
            owner=self.foreign,
            title="Foreign private",
            publication_status="private",
        )
        SourceAuthor.objects.create(
            source=foreign_source, author=author_a, position=73891
        )
        self.client.force_login(self.owner)
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="delete_author",
                content_type=ContentType.objects.get_for_model(Author),
            )
        )
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(_admin_url(Author, "delete", author_a.pk))
        # A blocked cascade fails closed before any related-name preview.
        self.assertEqual(response.status_code, 403)
        body = response.content.decode()
        self.assertNotIn("73891", body)
        self.assertNotIn("Foreign private", body)


class InlineReadContractTests(PersistenceFixture):
    """Owned inline rows render read-only via parent authority without
    requiring child-model permissions."""

    def test_contributor_reads_authors_on_published_source(self):
        author = Author.objects.create(
            owner=self.foreign,
            first_names="Ada",
            last_names="Lovelace",
            publication_status="published",
        )
        source = Source.objects.create(
            owner=self.foreign,
            title="Published source",
            publication_status="published",
        )
        SourceAuthor.objects.create(source=source, author=author, position=1)
        contributor = User.objects.create_user(username="p-contrib", is_staff=True)
        self.client.force_login(contributor)
        for state in ("published", "archived"):
            with self.subTest(state=state):
                Source.objects.filter(pk=source.pk).update(publication_status=state)
                response = self.client.get(_admin_url(Source, "change", source.pk))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Lovelace")
                self.assertNotContains(response, 'name="sourceauthors-0-position"')
                self.assertNotContains(response, 'name="sourceauthors-0-DELETE"')
                self.assertNotContains(response, 'name="_save"')
                with self.assertLogs("django.request", level="WARNING"):
                    response = self.client.post(
                        _admin_url(Source, "change", source.pk),
                        {
                            "title": "Forbidden",
                            "type": "misc",
                            "sourceauthors-TOTAL_FORMS": "1",
                            "sourceauthors-INITIAL_FORMS": "1",
                            "sourceauthors-0-id": source.sourceauthors.get().pk,
                            "sourceauthors-0-author": author.pk,
                            "sourceauthors-0-position": "2",
                            "_save": "Save",
                        },
                    )
                self.assertEqual(response.status_code, 403)
                source.refresh_from_db()
                self.assertEqual(source.title, "Published source")
                self.assertEqual(source.publication_status, state)
                self.assertEqual(source.content_revision, 1)
                self.assertEqual(source.sourceauthors.get().position, 1)


class FreshAuthorityHookTests(PersistenceFixture):
    """Authority is re-read at save hooks, not just at form validation."""

    def test_reference_revoked_after_validation_denies(self):
        """A reference made inaccessible between form validation and the
        persistence hook must roll the whole save back."""
        source = Source.objects.create(
            owner=self.owner, title="Ref test", publication_status="private"
        )
        grantee = Author.objects.create(
            owner=self.foreign,
            first_names="Ada",
            last_names="Lovelace",
            publication_status="private",
        )
        # Owner has read on the author via an editor grant, then loses it.
        ObjectEditorGrant.objects.create(
            content_object=grantee, editor=self.owner, granted_by=self.foreign
        )
        self.client.force_login(self.owner)
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="change_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )

        # Scoped hook: revoke the grant at form-save time (after validation).
        original = PolicyAdminMixin.save_model
        calls = []

        def revoke_then_save(admin_self, request, obj, form, change):
            # The form already validated; now the reference is revoked.
            calls.append(obj.pk)
            ObjectEditorGrant.objects.filter(
                object_id=grantee.pk, editor=self.owner
            ).delete()
            return original(admin_self, request, obj, form, change)

        with (
            patch.object(PolicyAdminMixin, "save_model", revoke_then_save),
            self.assertLogs("django.request", level="WARNING") as logged,
        ):
            response = self.client.post(
                _admin_url(Source, "change", source.pk),
                data={
                    "title": "Must roll back",
                    "type": "misc",
                    "licence": "",
                    "sourceauthors-TOTAL_FORMS": "1",
                    "sourceauthors-INITIAL_FORMS": "0",
                    "sourceauthors-0-id": "",
                    "sourceauthors-0-author": str(grantee.pk),
                    "sourceauthors-0-position": "1",
                    "_save": "Save",
                },
            )
        # Whole save denied/rolled back: no SourceAuthor row, no audit event.
        self.assertEqual(calls, [source.pk])
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", "\n".join(logged.output))
        source.refresh_from_db()
        self.assertEqual(source.title, "Ref test")
        self.assertEqual(source.content_revision, 1)
        self.assertEqual(source.owner_id, self.owner.pk)
        self.assertEqual(source.publication_status, "private")
        self.assertFalse(
            SourceAuthor.objects.filter(source=source, author=grantee).exists()
        )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                object_id=source.pk,
            ).exists()
        )
