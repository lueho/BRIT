from django.db.models.signals import post_save
from django.urls import reverse

from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import Author, Source, check_url_valid


def setUpModule():
    post_save.disconnect(check_url_valid, sender=Source)


def tearDownModule():
    post_save.connect(check_url_valid, sender=Source)


class SourceBibtexArticleImportViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_source"]

    def test_get_source_create_page_contains_link_to_bibtex_import(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("source-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Source creation mode")
        self.assertContains(response, "Manual")
        self.assertContains(response, "BibTeX @article")
        self.assertContains(response, reverse("source-bibtex-article-import"))

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(reverse("source-bibtex-article-import"))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_authenticated_without_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("source-bibtex-article-import"))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("source-bibtex-article-import"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create New Source from BibTeX @article")
        self.assertContains(response, "Source creation mode")
        self.assertContains(response, "Manual")
        self.assertContains(response, "BibTeX @article")
        self.assertContains(response, reverse("source-create"))

    def test_post_http_302_creates_source_from_bibtex_entry(self):
        self.client.force_login(self.member)
        author = Author.objects.create(
            owner=self.member,
            first_names="Ada",
            last_names="Lovelace",
        )

        response = self.client.post(
            reverse("source-bibtex-article-import"),
            data={
                "bibtex_entry": """
                @article{Lovelace1843,
                    author = {Lovelace, Ada},
                    title = {Notes on the Analytical Engine},
                    journal = {Scientific Memoirs},
                    year = {1843},
                    volume = {3},
                    number = {4},
                    pages = {666--699},
                    month = {Dec}
                }
                """,
            },
        )

        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(citation_key="Lovelace 1843")
        self.assertEqual(response.url, source.get_absolute_url())
        self.assertEqual(source.type, "article")
        self.assertEqual(source.title, "Notes on the Analytical Engine")
        self.assertEqual(source.journal, "Scientific Memoirs")
        self.assertEqual(source.volume, "3")
        self.assertEqual(source.number, "4")
        self.assertEqual(source.pages, "666--699")
        self.assertEqual(source.month, "dec")
        self.assertEqual(source.year, 1843)
        self.assertEqual(source.sourceauthors.count(), 1)
        self.assertEqual(source.sourceauthors.get().author_id, author.pk)
