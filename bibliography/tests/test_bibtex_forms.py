from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from utils.object_management.models import User

from ..forms import SourceBibtexArticleImportForm
from ..models import Author


class SourceBibtexArticleImportFormTestCase(TestCase):
    def test_form_creates_article_source_from_bibtex_with_existing_authors(self):
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
                    author = {Lovelace, Ada and Hopper, Grace},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843},
                    volume = {3},
                    number = {4},
                    pages = {666--699},
                    month = {Dec}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        source = form.create_source(owner=owner)

        self.assertEqual(source.type, "article")
        self.assertEqual(source.abbreviation, "Lovelace1843")
        self.assertEqual(source.title, "Notes on the Analytical Engine")
        self.assertEqual(source.journal, "Scientific Memoirs")
        self.assertEqual(source.volume, "3")
        self.assertEqual(source.issue, "4")
        self.assertEqual(source.pages, "666-699")
        self.assertEqual(source.month, "dec")
        self.assertEqual(source.year, 1843)
        self.assertEqual(
            list(
                source.sourceauthors.order_by("position").values_list(
                    "author_id",
                    flat=True,
                )
            ),
            [ada.pk, grace.pk],
        )

    def test_form_creates_missing_authors_when_user_has_permission(self):
        owner = User.objects.create(username="owner")
        owner.user_permissions.add(Permission.objects.get(codename="add_author"))
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        source = form.create_source(owner=owner)

        self.assertEqual(source.sourceauthors.count(), 1)
        created_author = source.sourceauthors.get().author
        self.assertEqual(created_author.first_names, "Ada")
        self.assertEqual(created_author.last_names, "Lovelace")
        self.assertEqual(created_author.owner, owner)

    def test_form_requires_add_author_permission_for_missing_authors(self):
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
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaisesMessage(
            ValidationError,
            "You need permission to create missing authors from BibTeX imports.",
        ):
            form.create_source(owner=owner)
