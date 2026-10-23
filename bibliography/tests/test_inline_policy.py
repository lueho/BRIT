import json

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from ..forms import SourceBibtexArticleImportForm
from ..models import Author, Source, SourceAuthor
from ..services import create_source_with_authors, resolve_author_for_source


def _permission(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


class InlinePolicyFixture(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator")
        self.creator.user_permissions.add(
            _permission(Source, "add_source"), _permission(Author, "add_author")
        )
        self.source_only = User.objects.create_user(username="source-only")
        self.source_only.user_permissions.add(_permission(Source, "add_source"))
        self.no_perms = User.objects.create_user(username="no-perms")
        self.other_owner = User.objects.create_user(username="other-owner")

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


class CreateSourceWithAuthorsTests(InlinePolicyFixture):
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

    def test_new_author_created_when_add_author_present(self):
        source = create_source_with_authors(
            self.creator,
            {"title": "New author", "type": "misc"},
            [{"first_names": "Grace", "last_names": "Hopper"}],
        )
        author = source.authors_ordered[0]
        self.assertEqual(author.last_names, "Hopper")
        self.assertEqual(author.owner, self.creator)
        self.assertEqual(author.publication_status, "private")

    def test_inaccessible_private_author_id_denied(self):
        with self.assertRaises(ValidationError):
            create_source_with_authors(
                self.creator,
                {"title": "Bad ref"},
                [{"id": self.private_foreign_author.pk}],
            )
        self.assertEqual(Source.objects.count(), 0)

    def test_inaccessible_private_author_name_not_reused(self):
        source = create_source_with_authors(
            self.creator,
            {"title": "Name lookup"},
            [{"first_names": "Secret", "last_names": "Writer"}],
        )
        author = source.authors_ordered[0]
        self.assertNotEqual(author.pk, self.private_foreign_author.pk)
        self.assertEqual(author.owner, self.creator)

    def test_duplicate_author_references_deduplicated(self):
        source = create_source_with_authors(
            self.creator,
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
                self.creator,
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
            self.creator,
            {
                "title": "Forged",
                "owner": self.other_owner,
                "publication_status": "published",
            },
            [],
        )
        self.assertEqual(source.owner, self.creator)
        self.assertEqual(source.publication_status, "private")

    def test_source_author_rows_need_no_own_permissions(self):
        source = create_source_with_authors(
            self.source_only,
            {"title": "Through rows"},
            [{"id": self.public_author.pk}],
        )
        self.assertEqual(SourceAuthor.objects.filter(source=source).count(), 1)


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
        sources = form.create_sources(owner=self.creator)
        self.assertEqual(len(sources), 2)
        writer = sources[1].authors_ordered[0]
        self.assertNotEqual(writer.pk, self.private_foreign_author.pk)
        self.assertEqual(writer.owner, self.creator)

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


class QuickCreateViewTests(InlinePolicyFixture):
    def test_author_quick_create_denied_without_add_author(self):
        self.client.force_login(self.no_perms)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "New", "last_names": "Person"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())

    def test_author_quick_create_returns_existing_accessible_author(self):
        self.client.force_login(self.no_perms)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.public_author.pk)

    def test_author_quick_create_does_not_reveal_private_author(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Secret", "last_names": "Writer"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()["id"], self.private_foreign_author.pk)

    def test_source_quick_create_denied_without_add_source(self):
        self.client.force_login(self.no_perms)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Nope"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Source.objects.count(), 0)

    def test_source_quick_create_with_accessible_author(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Quick source",
                    "year": 2021,
                    "authors": [{"id": self.public_author.pk}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        source = Source.objects.get()
        self.assertEqual(source.owner, self.source_only)
        self.assertEqual(
            [a.pk for a in source.authors_ordered], [self.public_author.pk]
        )

    def test_source_quick_create_new_author_denied_atomically(self):
        self.client.force_login(self.source_only)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Rollback me",
                    "authors": [
                        {"id": self.public_author.pk},
                        {"first_names": "New", "last_names": "Person"},
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Source.objects.count(), 0)
        self.assertFalse(Author.objects.filter(last_names="Person").exists())

    def test_source_quick_delete_uses_delete_policy(self):
        self.creator.user_permissions.add(_permission(Source, "delete_source"))
        source = Source.objects.create(owner=self.creator, title="Mine")
        foreign = Source.objects.create(
            owner=self.other_owner, title="Foreign", publication_status="private"
        )
        self.client.force_login(self.creator)
        response = self.client.generic(
            "DELETE",
            reverse("source-quick-create"),
            data=json.dumps({"id": foreign.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.generic(
            "DELETE",
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=source.pk).exists())

    def test_referenced_source_not_deleted(self):
        self.creator.user_permissions.add(_permission(Source, "delete_source"))
        source = Source.objects.create(owner=self.creator, title="Cited")
        SourceAuthor.objects.create(
            source=source, author=self.public_author, position=1
        )
        self.client.force_login(self.creator)
        from materials.models import Material, Sample

        material = Material.objects.create(name="Referenced Material")
        sample = Sample.objects.create(
            owner=self.creator, name="Referenced Sample", material=material
        )
        sample.sources.add(source)
        response = self.client.generic(
            "DELETE",
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())


class ResolveAuthorHelperTests(InlinePolicyFixture):
    def test_non_dict_entry_rejected(self):
        with self.assertRaises(ValidationError):
            resolve_author_for_source(self.creator, "Ada", allow_create=True)

    def test_nonexistent_id_rejected_uniformly(self):
        with self.assertRaises(ValidationError) as ctx:
            resolve_author_for_source(self.creator, {"id": 424242}, allow_create=True)
        self.assertIn("not accessible", str(ctx.exception))

    def test_unknown_author_type_rejected_without_writes(self):
        with self.assertRaises(ValidationError):
            resolve_author_for_source(
                self.creator,
                {"author_type": "robot", "last_names": "Unit"},
                allow_create=True,
            )
        self.assertFalse(
            Author.objects.filter(last_names="Unit").exists(),
            "A rejected author_type must not fall through to person creation.",
        )

    def test_compound_helper_rolls_back_on_unknown_author_type(self):
        with self.assertRaises(ValidationError):
            create_source_with_authors(
                self.creator,
                {"title": "T", "type": "misc"},
                [
                    {"last_names": "First", "first_names": "A"},
                    {"author_type": "robot", "last_names": "Unit"},
                ],
            )
        self.assertFalse(Source.objects.exists())
        self.assertFalse(Author.objects.filter(last_names="First").exists())
        self.assertFalse(SourceAuthor.objects.exists())


class SourceInlineHttpTests(InlinePolicyFixture):
    """The normal Source create/update formset must reject forged author
    references against the actor-visible Author queryset."""

    def _inline_data(self, rows):
        """rows: list of (row_id_or_empty, author_pk) tuples."""
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
        self.source_only.user_permissions.add(_permission(Source, "change_source"))
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


class QuickEndpointPayloadTests(InlinePolicyFixture):
    def test_non_dict_json_rejected(self):
        self.client.force_login(self.creator)
        for url_name in ("author-quick-create", "source-quick-create"):
            response = self.client.post(
                reverse(url_name),
                data=json.dumps(["not", "a", "dict"]),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, msg=url_name)
        self.assertEqual(Source.objects.count(), 0)
