from io import StringIO

from django.core.management import call_command
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

from utils.object_management.models import ReviewAction, User
from utils.tests.testcases import ViewWithPermissionsTestCase

from ..forms import SourceBibtexArticleImportForm
from ..models import Author, Source, SourceAuthor, check_url_valid


def setUpModule():
    post_save.disconnect(check_url_valid, sender=Source)


def tearDownModule():
    post_save.connect(check_url_valid, sender=Source)


class SourceBibtexBulkImportFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._role_output = StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

    def test_form_creates_multiple_sources_from_multiple_entries(self):
        owner = User.objects.create(username="owner")
        ada = Author.objects.create(
            owner=owner,
            first_names="Ada",
            last_names="Lovelace",
        )
        grace = Author.objects.create(
            owner=owner,
            first_names="Grace",
            last_names="Hopper",
        )
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843}
                }

                @article{Hopper1952,
                    author = {Hopper, Grace},
                    title = {The Education of a Computer},
                    journal = {Proceedings of the ACM},
                    year = {1952}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        sources = form.create_sources(owner=owner)

        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0].abbreviation, "Lovelace 1843")
        self.assertEqual(sources[1].abbreviation, "Hopper 1952")
        self.assertEqual(sources[0].sourceauthors.get().author_id, ada.pk)
        self.assertEqual(sources[1].sourceauthors.get().author_id, grace.pk)

    def test_single_source_helper_rejects_multiple_entries(self):
        owner = User.objects.create(username="owner")
        Author.objects.create(
            owner=owner,
            first_names="Ada",
            last_names="Lovelace",
        )
        Author.objects.create(
            owner=owner,
            first_names="Grace",
            last_names="Hopper",
        )
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843}
                }

                @article{Hopper1952,
                    author = {Hopper, Grace},
                    title = {The Education of a Computer},
                    journal = {Proceedings of the ACM},
                    year = {1952}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        author_count = Author.objects.count()
        with self.assertRaisesMessage(
            ValueError,
            "The BibTeX import form contains multiple entries.",
        ):
            form.create_source(owner=owner)

        # The rejection must happen before any persistence: no sources,
        # no association rows, no audit events, no author mutations.
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(SourceAuthor.objects.count(), 0)
        self.assertEqual(Author.objects.count(), author_count)
        self.assertEqual(ReviewAction.objects.count(), 0)

    def test_single_source_helper_rejects_multi_entry_with_new_authors(self):
        owner = User.objects.create(username="owner")
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843}
                }

                @article{Hopper1952,
                    author = {Hopper, Grace},
                    title = {The Education of a Computer},
                    journal = {Proceedings of the ACM},
                    year = {1952}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaisesMessage(
            ValueError,
            "The BibTeX import form contains multiple entries.",
        ):
            form.create_source(owner=owner)

        # Even though every entry would be individually creatable, the
        # multi-entry rejection leaves no rows or audits behind.
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(SourceAuthor.objects.count(), 0)
        self.assertFalse(Author.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), 0)


class SourceBibtexBulkImportViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_source"]

    def test_post_http_302_creates_multiple_sources_from_bibtex_entries(self):
        self.client.force_login(self.member)
        ada = Author.objects.create(
            owner=self.member,
            first_names="Ada",
            last_names="Lovelace",
        )
        grace = Author.objects.create(
            owner=self.member,
            first_names="Grace",
            last_names="Hopper",
        )

        response = self.client.post(
            reverse("source-bibtex-article-import"),
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843}
                }

                @article{Hopper1952,
                    author = {Hopper, Grace},
                    title = {The Education of a Computer},
                    journal = {Proceedings of the ACM},
                    year = {1952}
                }
                """,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("source-list-owned"))
        self.assertTrue(Source.objects.filter(citation_key="Lovelace 1843").exists())
        self.assertTrue(Source.objects.filter(citation_key="Hopper 1952").exists())
        self.assertEqual(
            Source.objects.get(citation_key="Lovelace 1843")
            .sourceauthors.get()
            .author_id,
            ada.pk,
        )
        self.assertEqual(
            Source.objects.get(citation_key="Hopper 1952")
            .sourceauthors.get()
            .author_id,
            grace.pk,
        )
