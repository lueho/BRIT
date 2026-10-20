"""Regressions for inline source/author creation policy.

HTTP-level classes exercise real request/response paths (test client,
rendered forms/widgets); service-level classes exercise the authoritative
write boundary directly. No test computes its expectations through the
policy implementation under test.
"""

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from materials.forms import AnalyticalMethodModelForm
from materials.models import AnalyticalMethod, Material, Sample
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
)
from utils.object_management.services import record_comment

from .. import services as services_module
from ..forms import SourceAuthorForm, SourceBibtexArticleImportForm
from ..models import Author, Licence, Source, SourceAuthor
from ..services import create_source_with_authors, resolve_author_for_source


def _perm(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


def _events(obj, action=None):
    qs = ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
    )
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class InlinePolicyFixture(TestCase):
    """Provisioned personas: registered contributor uses only role manifest
    capabilities; narrower actors get explicit single-model permissions."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())
        cls.registered = Group.objects.get(name="registered")

    def setUp(self):
        self.contributor = User.objects.create_user(username="creator")
        self.contributor.groups.add(self.registered)

        self.source_only = User.objects.create_user(username="source-only")
        # New users auto-join the registered group via post_save; narrow
        # personas must be cleared first so only the explicit perms apply.
        self.source_only.groups.clear()
        self.source_only.user_permissions.add(_perm(Source, "add_source"))

        self.method_only = User.objects.create_user(username="method-only")
        self.method_only.groups.clear()
        self.method_only.user_permissions.add(
            _perm(AnalyticalMethod, "add_analyticalmethod"),
            _perm(AnalyticalMethod, "change_analyticalmethod"),
            _perm(AnalyticalMethod, "view_analyticalmethod"),
        )

        self.staff_only = User.objects.create_user(username="staff-only", is_staff=True)
        self.staff_only.groups.clear()

        self.inactive = User.objects.create_user(username="inactive", is_active=False)
        self.inactive.groups.add(self.registered)

        self.no_perms = User.objects.create_user(username="no-perms")
        self.no_perms.groups.clear()
        self.other_owner = User.objects.create_user(username="other-owner")
        self.other_owner.groups.clear()

        self.public_author = Author.objects.create(
            owner=self.other_owner,
            first_names="Ada",
            last_names="Lovelace",
            publication_status="published",
        )
        self.private_foreign_author = Author.objects.create(
            owner=self.other_owner,
            first_names="Secret",
            last_names="Writer",
            publication_status="private",
        )

    def _bibtex_form(self, entries):
        return SourceBibtexArticleImportForm(data={"bibtex_entry": entries})


class QuickCreatePolicyTests(InlinePolicyFixture):
    """Quick-create endpoints must scope references, authorize inside the
    write boundary, and audit creations."""

    def test_source_quick_create_with_public_author(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {"title": "Quick source", "authors": [{"id": self.public_author.pk}]}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        source = Source.objects.get()
        self.assertEqual(source.owner, self.contributor)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )
        self.assertEqual(_events(source, "created").count(), 1)

    def test_source_quick_create_foreign_private_author_denied(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Bad ref",
                    "authors": [{"id": self.private_foreign_author.pk}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(SourceAuthor.objects.count(), 0)

    def test_source_quick_create_partial_authors_rolled_back(self):
        self.client.force_login(self.contributor)
        author_count = Author.objects.count()
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Rollback me",
                    "authors": [
                        {"first_names": "New", "last_names": "Person"},
                        {"id": self.private_foreign_author.pk},
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Author.objects.count(), author_count)

    def test_source_quick_create_new_author_without_add_denied(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Needs new author",
                    "authors": [{"first_names": "New", "last_names": "Person"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Source.objects.count(), 0)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())

    def test_author_quick_create_reuses_public_without_add(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.public_author.pk)
        self.assertEqual(Author.objects.count(), 2)

    def test_author_quick_create_new_without_add_denied(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "New", "last_names": "Person"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())

    def test_author_quick_create_does_not_reveal_private_author(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Secret", "last_names": "Writer"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()["id"], self.private_foreign_author.pk)

    def test_author_quick_create_records_audit_on_new(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Grace", "last_names": "Hopper"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        author = Author.objects.get(last_names="Hopper")
        self.assertEqual(author.owner, self.contributor)
        self.assertEqual(author.publication_status, "private")
        self.assertEqual(_events(author, "created").count(), 1)

    def test_inactive_actor_denied(self):
        self.client.force_login(self.inactive)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )
        # Django's login machinery treats inactive users as anonymous:
        # the only honest denial is the login redirect.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Author.objects.count(), 2)

    def test_anonymous_redirected(self):
        for name in ("author-quick-create", "source-quick-create"):
            response = self.client.post(
                reverse(name), data="{}", content_type="application/json"
            )
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("login", response["Location"])

    def test_staff_only_cannot_quick_create(self):
        self.client.force_login(self.staff_only)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Grace", "last_names": "Hopper"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(last_names="Hopper").exists())

    def test_forged_server_fields_ignored(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Forged",
                    "owner": self.other_owner.pk,
                    "publication_status": "published",
                    "content_revision": 99,
                    "authors": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        source = Source.objects.get()
        self.assertEqual(source.owner, self.contributor)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.content_revision, 1)


class QuickEndpointPayloadTests(InlinePolicyFixture):
    def test_non_dict_json_rejected(self):
        self.client.force_login(self.contributor)
        for url_name in ("author-quick-create", "source-quick-create"):
            response = self.client.post(
                reverse(url_name),
                data=json.dumps(["not", "a", "dict"]),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, msg=url_name)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Author.objects.count(), 2)

    def test_invalid_json_rejected(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("source-quick-create"),
            data=b"not json at all",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class QuickDeletePolicyTests(InlinePolicyFixture):
    def _delete(self, pk):
        return self.client.generic(
            "DELETE",
            reverse("source-quick-create"),
            data=json.dumps({"id": pk}),
            content_type="application/json",
        )

    def setUp(self):
        super().setUp()
        self.source_only.user_permissions.add(_perm(Source, "delete_source"))
        self.mine = Source.objects.create(
            owner=self.source_only, title="Mine", publication_status="private"
        )

    def test_delete_own_unreferenced_private_allowed_without_add(self):
        self.source_only.user_permissions.remove(_perm(Source, "add_source"))
        self.client.force_login(self.source_only)
        response = self._delete(self.mine.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=self.mine.pk).exists())

    def test_delete_foreign_invisible_returns_404(self):
        foreign = Source.objects.create(
            owner=self.other_owner, title="Hidden", publication_status="private"
        )
        self.client.force_login(self.source_only)
        response = self._delete(foreign.pk)
        self.assertEqual(response.status_code, 404)

    def test_delete_cited_source_denied(self):

        material = Material.objects.create(
            owner=self.source_only, name="M", publication_status="published"
        )
        sample = Sample.objects.create(
            owner=self.source_only,
            name="S",
            material=material,
            publication_status="published",
        )
        sample.sources.add(self.mine)
        self.client.force_login(self.source_only)
        response = self._delete(self.mine.pk)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Source.objects.filter(pk=self.mine.pk).exists())

    def test_delete_frozen_source_denied(self):
        self.mine.publication_status = "published"
        self.mine.save()
        self.client.force_login(self.source_only)
        response = self._delete(self.mine.pk)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Source.objects.filter(pk=self.mine.pk).exists())

    def test_delete_keeps_independent_authors(self):
        SourceAuthor.objects.create(
            source=self.mine, author=self.public_author, position=1
        )
        self.client.force_login(self.source_only)
        response = self._delete(self.mine.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Author.objects.filter(pk=self.public_author.pk).exists())
        self.assertEqual(SourceAuthor.objects.filter(source_id=self.mine.pk).count(), 0)


class ApiSourceCreatePolicyTests(InlinePolicyFixture):
    def _post(self, user, payload):
        self.client.force_login(user)
        return self.client.post(
            reverse("api-source-create"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_api_create_with_accessible_author(self):
        response = self._post(
            self.contributor,
            {
                "title": "API source",
                "type": "article",
                "authors": [{"id": self.public_author.pk}],
            },
        )
        self.assertEqual(response.status_code, 201)
        source = Source.objects.get()
        self.assertEqual(source.owner, self.contributor)
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )
        self.assertEqual(_events(source, "created").count(), 1)

    def test_api_create_foreign_private_author_denied(self):
        response = self._post(
            self.contributor,
            {
                "title": "Bad ref",
                "type": "article",
                "authors": [{"id": self.private_foreign_author.pk}],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)

    def test_api_create_rolls_back_partial_authors(self):
        author_count = Author.objects.count()
        response = self._post(
            self.contributor,
            {
                "title": "Rollback",
                "type": "misc",
                "authors": [
                    {"first_names": "New", "last_names": "Person"},
                    {"id": 424242},
                ],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Author.objects.count(), author_count)

    def test_api_create_new_author_without_add_denied(self):
        response = self._post(
            self.source_only,
            {
                "title": "Needs author",
                "type": "misc",
                "authors": [{"first_names": "New", "last_names": "Person"}],
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())


class BibtexImportPolicyTests(InlinePolicyFixture):
    ENTRY = (
        "@article{key1, author={Doe, John}, title={First}, "
        "journal={Journal of Testing}, year={2020}}\n"
        "@article{key2, author={%s}, title={Second}, "
        "journal={Journal of Testing}, year={2021}}"
    )

    def test_bibtex_import_uses_scoped_author_resolution(self):
        bibtex = self.ENTRY % "Writer, Secret"
        form = self._bibtex_form(bibtex)
        self.assertTrue(form.is_valid(), form.errors)
        sources = form.create_sources(owner=self.contributor)
        self.assertEqual(len(sources), 2)
        writer = sources[1].authors_ordered[0]
        self.assertNotEqual(writer.pk, self.private_foreign_author.pk)
        self.assertEqual(writer.owner, self.contributor)

    def test_bibtex_later_failure_rolls_back_earlier_rows(self):
        bibtex = (
            "@article{key1, author={Lovelace, Ada}, title={First}, "
            "journal={Journal of Testing}, year={2020}}\n"
            "@article{key2, author={Newperson, Xenia}, title={Second}, "
            "journal={Journal of Testing}, year={2021}}"
        )
        form = self._bibtex_form(bibtex)
        self.assertTrue(form.is_valid(), form.errors)
        source_count = Source.objects.count()
        author_count = Author.objects.count()
        with self.assertRaises(ValidationError):
            form.create_sources(owner=self.source_only)
        self.assertEqual(Source.objects.count(), source_count)
        self.assertEqual(SourceAuthor.objects.count(), 0)
        self.assertEqual(Author.objects.count(), author_count)

    def test_bibtex_reuses_accessible_existing_author(self):
        bibtex = (
            "@article{key1, author={Lovelace, Ada}, title={First}, "
            "journal={Journal of Testing}, year={2020}}\n"
            "@article{key2, author={Lovelace, Ada}, title={Second}, "
            "journal={Journal of Testing}, year={2021}}"
        )
        form = self._bibtex_form(bibtex)
        self.assertTrue(form.is_valid(), form.errors)
        sources = form.create_sources(owner=self.source_only)
        self.assertEqual(len(sources), 2)
        for source in sources:
            self.assertEqual(source.authors_ordered[0].pk, self.public_author.pk)
            self.assertEqual(source.type, "article")
            self.assertEqual(source.owner, self.source_only)


class SourceInlineHttpTests(InlinePolicyFixture):
    """The regular Source create/update inline formset must scope author
    choices to actor-visible records."""

    def _inline_data(self, rows):
        initial = sum(1 for row_id, _ in rows if row_id)
        data = {
            "sourceauthors-TOTAL_FORMS": len(rows),
            "sourceauthors-INITIAL_FORMS": initial,
            "sourceauthors-MIN_NUM_FORMS": 0,
            "sourceauthors-MAX_NUM_FORMS": 1000,
        }
        for i, (row_id, author_pk) in enumerate(rows):
            data[f"sourceauthors-{i}-id"] = row_id
            data[f"sourceauthors-{i}-source"] = ""
            data[f"sourceauthors-{i}-author"] = author_pk
        return data

    def test_source_create_with_inaccessible_author_writes_nothing(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-create"),
            {
                "title": "Forged author reference",
                "type": "misc",
                **self._inline_data([("", self.private_foreign_author.pk)]),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(SourceAuthor.objects.count(), 0)

    def test_source_create_with_accessible_author_needs_no_add_author(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-create"),
            {
                "title": "Accessible author",
                "type": "misc",
                **self._inline_data([("", self.public_author.pk)]),
            },
        )
        self.assertEqual(response.status_code, 302)
        source = Source.objects.get()
        self.assertEqual(source.owner, self.source_only)
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )

    def test_source_update_rejects_inaccessible_author_swap(self):
        self.source_only.user_permissions.add(_perm(Source, "change_source"))
        source = Source.objects.create(
            owner=self.source_only, title="Updatable", publication_status="private"
        )
        row = SourceAuthor.objects.create(
            source=source, author=self.public_author, position=1
        )
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-update", kwargs={"pk": source.pk}),
            {
                "title": "Updatable",
                "type": "misc",
                **self._inline_data(
                    [
                        (row.pk, self.public_author.pk),
                        ("", self.private_foreign_author.pk),
                    ]
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(source.sourceauthors.values_list("author_id", flat=True)),
            [self.public_author.pk],
        )


class WidgetCapabilityRenderTests(InlinePolicyFixture):
    """The rendered source widget must reflect the actor's real create
    capabilities — creation affordances only appear when the policy allows."""

    def _render_method_form(self, user, method):
        request = SimpleNamespace(user=user)
        form = AnalyticalMethodModelForm(request=request, instance=method)
        return form["sources"].as_widget()

    def setUp(self):
        super().setUp()
        self.method = AnalyticalMethod.objects.create(
            owner=self.contributor, name="Method", publication_status="private"
        )

    def test_contributor_widget_offers_source_and_author_create(self):
        rendered = self._render_method_form(self.contributor, self.method)
        self.assertIn('data-quick-create-url="', rendered)
        self.assertIn("/sources/quick-create/", rendered)
        self.assertIn('data-author-quick-create-url="', rendered)
        self.assertIn("/authors/quick-create/", rendered)

    def test_method_only_widget_offers_neither_create(self):
        method = AnalyticalMethod.objects.create(
            owner=self.method_only, name="Theirs", publication_status="private"
        )
        rendered = self._render_method_form(self.method_only, method)
        self.assertNotIn("data-quick-create-url", rendered)
        self.assertNotIn("data-author-quick-create-url", rendered)
        self.assertNotIn("/sources/quick-create/", rendered)
        self.assertNotIn("/authors/quick-create/", rendered)

    def test_source_only_widget_search_without_author_create(self):
        rendered = self._render_method_form(self.source_only, self.method)
        self.assertIn("/sources/quick-create/", rendered)
        self.assertIn('data-author-autocomplete-url="', rendered)
        self.assertNotIn("data-author-quick-create-url", rendered)
        self.assertNotIn("/authors/quick-create/", rendered)


class ModalAndAutocompleteTests(InlinePolicyFixture):
    def test_source_modal_create_success(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("source-create-modal"), {"title": "Modal source", "type": "misc"}
        )
        self.assertIn(response.status_code, (204, 302), response.status_code)
        self.assertTrue(Source.objects.filter(title="Modal source").exists())

    def test_author_modal_create_success(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("author-create-modal"),
            {"author_type": "person", "first_names": "Modal", "last_names": "Author"},
        )
        self.assertIn(response.status_code, (204, 302), response.status_code)
        self.assertTrue(Author.objects.filter(last_names="Author").exists())

    def test_autocomplete_lists_new_records(self):
        Author.objects.create(
            owner=self.contributor,
            first_names="Auto",
            last_names="Complete",
            publication_status="private",
        )
        Source.objects.create(owner=self.contributor, title="Autocomplete source")
        self.client.force_login(self.contributor)
        for url_name, text in (
            ("author-autocomplete", "Complete"),
            ("source-autocomplete", "Autocomplete source"),
        ):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)
            self.assertIn(text, response.content.decode())


class CreateSourceWithAuthorsTests(InlinePolicyFixture):
    """Direct service contract: authoritative checks inside the boundary."""

    def test_actor_without_add_source_is_denied(self):
        with self.assertRaises(PermissionDenied):
            create_source_with_authors(self.no_perms, {"title": "Denied"}, [])
        self.assertEqual(Source.objects.count(), 0)

    def test_existing_accessible_author_works_without_add_author(self):
        source = create_source_with_authors(
            self.source_only,
            {"title": "With existing author", "type": "misc"},
            [{"id": self.public_author.pk}],
        )
        self.assertEqual(source.owner, self.source_only)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )
        self.assertEqual(_events(source, "created").count(), 1)
        self.assertEqual(_events(self.public_author).count(), 0)

    def test_new_author_without_add_author_denied_atomically(self):
        with self.assertRaises(PermissionDenied):
            create_source_with_authors(
                self.source_only,
                {"title": "Needs new author"},
                [
                    {"id": self.public_author.pk},
                    {"first_names": "New", "last_names": "Person"},
                ],
            )
        self.assertEqual(Source.objects.count(), 0)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())

    def test_new_author_created_and_audited_when_add_author_present(self):
        source = create_source_with_authors(
            self.contributor,
            {"title": "New author", "type": "misc"},
            [{"first_names": "Grace", "last_names": "Hopper"}],
        )
        author = source.authors_ordered[0]
        self.assertEqual(author.last_names, "Hopper")
        self.assertEqual(author.owner, self.contributor)
        self.assertEqual(author.publication_status, "private")
        self.assertEqual(_events(author, "created").count(), 1)

    def test_inaccessible_private_author_id_denied_uniformly(self):
        with self.assertRaises(ValidationError) as ctx:
            create_source_with_authors(
                self.contributor,
                {"title": "Bad ref"},
                [{"id": self.private_foreign_author.pk}],
            )
        self.assertIn("not accessible", str(ctx.exception))
        self.assertEqual(Source.objects.count(), 0)

    def test_inaccessible_private_author_name_not_reused(self):
        source = create_source_with_authors(
            self.contributor,
            {"title": "Name lookup"},
            [{"first_names": "Secret", "last_names": "Writer"}],
        )
        author = source.authors_ordered[0]
        self.assertNotEqual(author.pk, self.private_foreign_author.pk)
        self.assertEqual(author.owner, self.contributor)

    def test_duplicate_author_references_deduplicated(self):
        source = create_source_with_authors(
            self.contributor,
            {"title": "Dupes"},
            [
                {"id": self.public_author.pk},
                {"first_names": "Ada", "last_names": "Lovelace"},
                {"id": self.public_author.pk},
            ],
        )
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )
        self.assertEqual(SourceAuthor.objects.filter(source=source).count(), 1)

    def test_invalid_later_entry_rolls_back_everything(self):
        author_count = Author.objects.count()
        with self.assertRaises(ValidationError):
            create_source_with_authors(
                self.contributor,
                {"title": "Rollback"},
                [
                    {"first_names": "Early", "last_names": "Bird"},
                    {"id": 999999},
                ],
            )
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(SourceAuthor.objects.count(), 0)
        self.assertEqual(Author.objects.count(), author_count)

    def test_source_owner_and_status_overrides_ignored(self):
        source = create_source_with_authors(
            self.contributor,
            {
                "title": "Forged",
                "owner": self.other_owner.pk,
                "publication_status": "published",
                "content_revision": 42,
                "approved_by_id": self.other_owner.pk,
                "approved_at": "2020-01-01T00:00:00Z",
                "submitted_at": "2020-01-01T00:00:00Z",
                "created_at": "2020-01-01T00:00:00Z",
            },
            [],
        )
        self.assertEqual(source.owner, self.contributor)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.content_revision, 1)
        self.assertIsNone(source.approved_by)
        self.assertIsNone(source.approved_at)
        self.assertIsNone(source.submitted_at)
        self.assertNotEqual(str(source.created_at)[:19], "2020-01-01T00:00:00")

    def test_reused_author_forged_fields_ignored(self):
        original = {
            "first_names": self.public_author.first_names,
            "last_names": self.public_author.last_names,
            "owner_id": self.public_author.owner_id,
            "publication_status": self.public_author.publication_status,
            "content_revision": self.public_author.content_revision,
        }
        author, created = resolve_author_for_source(
            self.contributor,
            {
                "id": self.public_author.pk,
                "first_names": "Forged",
                "last_names": "Names",
                "owner": self.contributor.pk,
                "publication_status": "private",
                "approved_by": self.contributor.pk,
            },
            allow_create=False,
        )
        self.assertFalse(created)
        self.public_author.refresh_from_db()
        for field, expected in original.items():
            self.assertEqual(getattr(self.public_author, field), expected)
        self.assertEqual(_events(self.public_author).count(), 0)

    def test_invisible_licence_reference_denied(self):
        private_licence = Licence.objects.create(
            owner=self.other_owner,
            name="Hidden Licence",
            publication_status="private",
        )
        with self.assertRaises(ValidationError):
            create_source_with_authors(
                self.contributor,
                {"title": "Lic ref", "licence": private_licence.pk},
                [],
            )
        self.assertEqual(Source.objects.count(), 0)

    def test_stale_actor_revocation_denied_inside_boundary(self):
        # Prime the create capability, then revoke add_source via a second
        # ORM instance: the boundary must re-read permissions, not reuse
        # the caller's stale cache.
        self.source_only.has_perm("bibliography.add_source")
        self.source_only.user_permissions.clear()
        self.source_only.user_permissions.add(_perm(Author, "add_author"))
        with self.assertRaises(PermissionDenied):
            create_source_with_authors(self.source_only, {"title": "Revoked"}, [])
        self.assertFalse(Source.objects.exists())


class ResolveAuthorHelperTests(InlinePolicyFixture):
    def test_non_dict_entry_rejected(self):
        with self.assertRaises(ValidationError):
            resolve_author_for_source(self.contributor, "Ada", allow_create=True)

    def test_nonexistent_id_rejected_uniformly(self):
        with self.assertRaises(ValidationError) as ctx:
            resolve_author_for_source(
                self.contributor, {"id": 424242}, allow_create=True
            )
        self.assertIn("not accessible", str(ctx.exception))

    def test_unknown_author_type_rejected_without_writes(self):
        with self.assertRaises(ValidationError):
            resolve_author_for_source(
                self.contributor,
                {"author_type": "robot", "last_names": "Unit"},
                allow_create=True,
            )
        self.assertFalse(Author.objects.filter(last_names="Unit").exists())

    def test_inactive_actor_cannot_reuse(self):
        with self.assertRaises(PermissionDenied):
            resolve_author_for_source(
                self.inactive, {"id": self.public_author.pk}, allow_create=False
            )

    def test_allow_create_cannot_bypass_missing_capability(self):
        # allow_create narrows, never widens: without add_author the call
        # must still go through authorize_create and fail closed.
        with self.assertRaises(PermissionDenied):
            resolve_author_for_source(
                self.source_only,
                {"first_names": "New", "last_names": "Person"},
                allow_create=True,
            )
        self.assertFalse(Author.objects.filter(last_names="Person").exists())


class ServiceAtomicityTests(InlinePolicyFixture):
    """A failure anywhere inside the write boundary rolls back every row."""

    def test_record_creation_failure_rolls_back_all(self):
        real = services_module.record_creation

        def flaky(actor, obj, _real=real):
            if isinstance(obj, Source):
                raise RuntimeError("audit write failed")
            return _real(actor, obj)

        with patch("bibliography.services.record_creation", flaky):
            with self.assertRaises(RuntimeError):
                create_source_with_authors(
                    self.contributor,
                    {"title": "Atomic"},
                    [{"first_names": "New", "last_names": "Person"}],
                )
        self.assertFalse(Source.objects.exists())
        self.assertFalse(Author.objects.filter(last_names="Person").exists())
        self.assertFalse(SourceAuthor.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), 0)

    def test_association_failure_rolls_back_source(self):
        def boom(**kwargs):
            raise RuntimeError("association failed")

        with patch.object(SourceAuthor.objects, "create", boom):
            with self.assertRaises(RuntimeError):
                create_source_with_authors(
                    self.contributor,
                    {"title": "Atomic"},
                    [{"id": self.public_author.pk}],
                )
        self.assertFalse(Source.objects.exists())
        self.assertEqual(_events(self.public_author).count(), 0)


class StaleReferenceActorTests(InlinePolicyFixture):
    """References are re-checked with the actor refreshed at the persistence
    edge — a revoked admin cache must not authorize foreign private refs."""

    def test_revoked_admin_cannot_reference_foreign_private_licence(self):
        admin_group = Group.objects.get(name="administrators")
        self.contributor.groups.add(admin_group)
        self.contributor.has_perm("object_management.administer_objects")
        hidden = Licence.objects.create(
            owner=self.other_owner,
            name="Hidden",
            publication_status="private",
        )

        real = services_module.resolve_author_for_source

        def revoke_admin(actor, author_data, *, allow_create):
            # Administrators membership is revoked mid-resolution through a
            # separate ORM instance; the caller's cached admin flag is stale.
            User.objects.filter(pk=actor.pk).first().groups.remove(admin_group)
            return real(actor, author_data, allow_create=allow_create)

        with patch.object(
            services_module, "resolve_author_for_source", side_effect=revoke_admin
        ):
            with self.assertRaises(PermissionDenied):
                create_source_with_authors(
                    self.contributor,
                    {"title": "Stale", "licence": hidden.pk},
                    [{"id": self.public_author.pk}],
                )
        self.assertFalse(Source.objects.exists())
        self.assertFalse(SourceAuthor.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), 0)


class QuickDeleteBoundaryTests(InlinePolicyFixture):
    """The delete boundary decides capability before reference inspection."""

    def _delete(self, pk):
        return self.client.generic(
            "DELETE",
            reverse("source-quick-create"),
            data=json.dumps({"id": pk}),
            content_type="application/json",
        )

    def setUp(self):
        super().setUp()
        self.cited = Source.objects.create(
            owner=self.source_only, title="Cited", publication_status="private"
        )
        self.other_owned_private = Source.objects.create(
            owner=self.source_only, title="Mine", publication_status="private"
        )

    def _cite(self, source):

        material = Material.objects.create(
            owner=self.source_only, name="M", publication_status="published"
        )
        sample = Sample.objects.create(
            owner=self.source_only,
            name="S",
            material=material,
            publication_status="published",
        )
        sample.sources.add(source)

    def test_reader_without_delete_gets_403_not_reference_leak(self):
        # Can read the (published) source but lacks delete_source: the
        # reference check must never run for them.
        reader = User.objects.create_user(username="reader")
        reader.groups.clear()
        reader.user_permissions.add(_perm(Source, "view_source"))
        self._cite(self.cited)
        self.cited.publication_status = "published"
        self.cited.save()
        self.client.force_login(reader)
        with patch(
            "bibliography.views.source_is_referenced",
            side_effect=AssertionError("reference probe ran before delete check"),
        ) as probe:
            response = self._delete(self.cited.pk)
        self.assertEqual(response.status_code, 403)
        probe.assert_not_called()
        self.assertTrue(Source.objects.filter(pk=self.cited.pk).exists())

    def test_frozen_own_cited_source_gets_403_not_400(self):
        self._cite(self.cited)
        self.cited.publication_status = "published"
        self.cited.save()
        self.source_only.user_permissions.add(_perm(Source, "delete_source"))
        self.client.force_login(self.source_only)
        response = self._delete(self.cited.pk)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Source.objects.filter(pk=self.cited.pk).exists())

    def test_owned_private_cited_400(self):
        self._cite(self.other_owned_private)
        self.source_only.user_permissions.add(_perm(Source, "delete_source"))
        self.client.force_login(self.source_only)
        response = self._delete(self.other_owned_private.pk)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Source.objects.filter(pk=self.other_owned_private.pk).exists())

    def test_unreferenced_authorized_delete_200(self):
        self.source_only.user_permissions.add(_perm(Source, "delete_source"))
        self.client.force_login(self.source_only)
        response = self._delete(self.other_owned_private.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=self.other_owned_private.pk).exists())


class FullInlineWorkflowTests(InlinePolicyFixture):
    """The original analytical-method -> inline source -> author path end to
    end with a provisioned registered contributor (zero manual perms)."""

    def test_full_inline_creation_sequence(self):
        self.client.force_login(self.contributor)

        response = self.client.post(
            reverse("analyticalmethod-create"), {"name": "Seq Method"}
        )
        self.assertEqual(response.status_code, 302)
        method = AnalyticalMethod.objects.get(name="Seq Method")

        response = self.client.get(
            reverse("analyticalmethod-update", kwargs={"pk": method.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sources/quick-create")
        self.assertContains(response, "authors/quick-create")

        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Byron"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        author = Author.objects.get(last_names="Byron")

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Seq source", "authors": [{"id": author.pk}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        source = Source.objects.get(title="Seq source")

        before_rev = method.content_revision
        response = self.client.post(
            reverse("analyticalmethod-update", kwargs={"pk": method.pk}),
            {"name": "Seq Method", "sources": [source.pk]},
        )
        self.assertEqual(response.status_code, 302)
        method.refresh_from_db()
        self.assertEqual(list(method.sources.all()), [source])
        self.assertEqual(method.content_revision, before_rev + 1)
        self.assertEqual(_events(method, "edited").count(), 1)

        for obj in (author, source):
            self.assertEqual(obj.owner, self.contributor)
            self.assertEqual(obj.publication_status, "private")
            self.assertEqual(obj.content_revision, 1)
            self.assertEqual(_events(obj, "created").count(), 1)
        row = SourceAuthor.objects.get(source=source)
        self.assertEqual(row.author, author)
        self.assertEqual(row.position, 1)


class SourceAuthorEditPolicyTests(InlinePolicyFixture):
    """SourceAuthor rows are owned children: edits follow the parent's edit
    capability, one parent revision+audit per change, and frozen parents deny."""

    def _fixture(self, status="private"):
        self.source_only.user_permissions.add(_perm(Source, "change_source"))
        source = Source.objects.create(
            owner=self.source_only, title="S", publication_status=status
        )
        return source

    def _update(self, source, rows, actor=None):
        initial = sum(1 for rid, _ in rows if rid)
        data = {
            "title": source.title,
            "type": source.type,
            "sourceauthors-TOTAL_FORMS": len(rows),
            "sourceauthors-INITIAL_FORMS": initial,
            "sourceauthors-MIN_NUM_FORMS": 0,
            "sourceauthors-MAX_NUM_FORMS": 1000,
        }
        for i, (rid, apk) in enumerate(rows):
            data[f"sourceauthors-{i}-id"] = rid
            data[f"sourceauthors-{i}-source"] = ""
            data[f"sourceauthors-{i}-author"] = apk
        self.client.force_login(actor or self.source_only)
        return self.client.post(
            reverse("source-update", kwargs={"pk": source.pk}), data
        )

    def test_owner_edit_in_review_bumps_one_revision(self):
        source = self._fixture(status="review")
        comment = record_comment(self.source_only, source, "Existing review feedback")
        rev = source.content_revision
        response = self._update(source, [("", self.public_author.pk)])
        self.assertEqual(response.status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        self.assertEqual(source.content_revision, rev + 1)
        self.assertEqual(_events(source, "edited").count(), 1)
        # Prior review history survives the revision bump.
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        self.assertEqual(
            list(source.sourceauthors.values_list("author_id", flat=True)),
            [self.public_author.pk],
        )

    def test_direct_editor_grant_allows_in_review_inline_edit(self):
        source = Source.objects.create(
            owner=self.source_only, title="S", publication_status="review"
        )
        comment = record_comment(self.source_only, source, "Existing review feedback")
        grant = ObjectEditorGrant.objects.create(
            content_object=source,
            editor=self.contributor,
            granted_by=self.source_only,
        )
        rev = source.content_revision
        response = self._update(
            source, [("", self.public_author.pk)], actor=self.contributor
        )
        self.assertEqual(response.status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        self.assertEqual(source.content_revision, rev + 1)
        self.assertEqual(_events(source, "edited").count(), 1)
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        self.assertEqual(self.contributor.user_permissions.count(), 0)

        # Revocation removes object-scoped access; this HTML write adapter
        # rejects the edit with 403 before processing the form.
        grant.delete()
        response = self._update(
            source, [("", self.public_author.pk)], actor=self.contributor
        )
        self.assertEqual(response.status_code, 403)
        # The detail read is denied too, and the autocomplete hides the record.
        detail = self.client.get(reverse("source-detail", kwargs={"pk": source.pk}))
        self.assertEqual(detail.status_code, 403)
        ac = self.client.get(reverse("source-autocomplete"), {"q": "S"})
        body = ac.json()
        items = body.get("results", body) if isinstance(body, dict) else body
        self.assertNotIn(source.pk, {item.get("id") for item in items})
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        self.assertEqual(source.content_revision, rev + 1)
        self.assertEqual(_events(source, "edited").count(), 1)
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        self.assertEqual(
            list(source.sourceauthors.values_list("author_id", flat=True)),
            [self.public_author.pk],
        )

    def test_group_editor_grant_allows_in_review_inline_edit(self):
        source = Source.objects.create(
            owner=self.source_only, title="S", publication_status="review"
        )
        comment = record_comment(self.source_only, source, "Existing review feedback")
        team = Group.objects.create(name="source-editors")
        team.user_set.add(self.contributor)
        ObjectGroupEditorGrant.objects.create(
            content_object=source,
            group=team,
            granted_by=self.source_only,
        )
        rev = source.content_revision
        response = self._update(
            source, [("", self.public_author.pk)], actor=self.contributor
        )
        self.assertEqual(response.status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        self.assertEqual(source.content_revision, rev + 1)
        self.assertEqual(_events(source, "edited").count(), 1)
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        self.assertEqual(self.contributor.user_permissions.count(), 0)

        # Revocation removes object-scoped access; this HTML write adapter
        # rejects the edit with 403 before processing the form.
        team.user_set.remove(self.contributor)
        response = self._update(
            source, [("", self.public_author.pk)], actor=self.contributor
        )
        self.assertEqual(response.status_code, 403)
        # The detail read is denied too, and the autocomplete hides the record.
        detail = self.client.get(reverse("source-detail", kwargs={"pk": source.pk}))
        self.assertEqual(detail.status_code, 403)
        ac = self.client.get(reverse("source-autocomplete"), {"q": "S"})
        body = ac.json()
        items = body.get("results", body) if isinstance(body, dict) else body
        self.assertNotIn(source.pk, {item.get("id") for item in items})
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "review")
        self.assertEqual(source.content_revision, rev + 1)
        self.assertEqual(_events(source, "edited").count(), 1)
        self.assertTrue(ReviewAction.objects.filter(pk=comment.pk).exists())
        self.assertEqual(
            list(source.sourceauthors.values_list("author_id", flat=True)),
            [self.public_author.pk],
        )

    def test_forged_existing_row_id_cannot_attach_to_other_source(self):
        source = self._fixture()
        foreign_source = Source.objects.create(
            owner=self.other_owner, title="Foreign", publication_status="published"
        )
        foreign_row = SourceAuthor.objects.create(
            source=foreign_source, author=self.public_author, position=1
        )
        response = self._update(source, [(foreign_row.pk, self.public_author.pk)])
        # Django resolves inline ids against the parent-scoped queryset: the
        # forged row is treated as a new row under *this* source and can never
        # steal or mutate the foreign parent's row.
        self.assertEqual(response.status_code, 302)
        foreign_row.refresh_from_db()
        self.assertEqual(foreign_row.source_id, foreign_source.pk)
        self.assertEqual(foreign_row.author_id, self.public_author.pk)
        self.assertEqual(
            list(source.sourceauthors.values_list("author_id", flat=True)),
            [self.public_author.pk],
        )

    def test_published_source_inline_denied(self):
        source = self._fixture(status="published")
        rev = source.content_revision
        response = self._update(source, [("", self.public_author.pk)])
        self.assertEqual(response.status_code, 403)
        source.refresh_from_db()
        self.assertEqual(source.content_revision, rev)
        self.assertEqual(source.sourceauthors.count(), 0)

    def test_archived_source_inline_denied(self):
        source = self._fixture(status="archived")
        rev = source.content_revision
        response = self._update(source, [("", self.public_author.pk)])
        self.assertEqual(response.status_code, 403)
        source.refresh_from_db()
        self.assertEqual(source.content_revision, rev)


class SourceAuthorFormScopeTests(InlinePolicyFixture):
    def test_form_author_choices_are_scoped_to_visible(self):
        request = SimpleNamespace(user=self.source_only)
        form = SourceAuthorForm(request=request)
        visible_ids = set(form.fields["author"].queryset.values_list("pk", flat=True))
        self.assertIn(self.public_author.pk, visible_ids)
        self.assertNotIn(self.private_foreign_author.pk, visible_ids)

    def test_standalone_form_without_request_sees_public_only(self):
        form = SourceAuthorForm()
        visible_ids = set(form.fields["author"].queryset.values_list("pk", flat=True))
        self.assertIn(self.public_author.pk, visible_ids)
        self.assertNotIn(self.private_foreign_author.pk, visible_ids)


class FreshReferenceBoundaryTests(InlinePolicyFixture):
    """A reference valid at resolution time is re-validated against fresh
    database state at the persistence edge."""

    def _wrap_flip(self, mutation):
        real = services_module.resolve_author_for_source

        def flip(actor, author_data, *, allow_create):
            author, created = real(actor, author_data, allow_create=allow_create)
            mutation(author)
            return author, created

        return services_module, flip

    def test_author_made_foreign_private_mid_resolution_denied(self):
        def flip(author):
            Author.objects.filter(pk=author.pk).update(
                publication_status="private", owner=self.other_owner
            )

        module, wrapper = self._wrap_flip(flip)
        with patch.object(module, "resolve_author_for_source", side_effect=wrapper):
            with self.assertRaises(PermissionDenied):
                create_source_with_authors(
                    self.contributor,
                    {"title": "Race"},
                    [{"id": self.public_author.pk}],
                )
        self.assertFalse(Source.objects.exists())
        self.assertFalse(SourceAuthor.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), 0)

    def test_author_deleted_mid_resolution_denied(self):
        def drop(author):
            Author.objects.filter(pk=author.pk).delete()

        module, wrapper = self._wrap_flip(drop)
        with patch.object(module, "resolve_author_for_source", side_effect=wrapper):
            with self.assertRaises(PermissionDenied):
                create_source_with_authors(
                    self.contributor,
                    {"title": "Race"},
                    [{"id": self.public_author.pk}],
                )
        self.assertFalse(Source.objects.exists())
        self.assertFalse(SourceAuthor.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), 0)

    def test_private_and_nonexistent_author_ids_identical_error(self):
        self.client.force_login(self.contributor)
        responses = []
        for ref in (self.private_foreign_author.pk, 424242):
            responses.append(
                self.client.post(
                    reverse("source-quick-create"),
                    data=json.dumps({"title": "T", "authors": [{"id": ref}]}),
                    content_type="application/json",
                )
            )
        self.assertEqual(responses[0].status_code, 400)
        self.assertEqual(responses[1].status_code, 400)
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertFalse(Source.objects.exists())
