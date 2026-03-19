from django.db.models.signals import post_save
from django.urls import reverse

from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import Author, Source, check_url_valid


def setUpModule():
    post_save.disconnect(check_url_valid, sender=Source)


def tearDownModule():
    post_save.connect(check_url_valid, sender=Source)


class SourceBibtexArticleNumberImportViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_source"]

    def test_post_http_302_creates_source_with_eid_from_bibtex_entry(self):
        self.client.force_login(self.member)
        sebastian = Author.objects.create(
            owner=self.member,
            first_names="Sebastian",
            last_names="Hagel",
        )
        bodo = Author.objects.create(
            owner=self.member,
            first_names="Bodo",
            last_names="Saake",
        )

        response = self.client.post(
            reverse("source-bibtex-article-import"),
            data={
                "bibtex_entry": """
                @Article{molecules25092165,
                    AUTHOR = {Hagel, Sebastian and Saake, Bodo},
                    TITLE = {Fractionation of Waste MDF by Steam Refining},
                    JOURNAL = {Molecules},
                    VOLUME = {25},
                    YEAR = {2020},
                    NUMBER = {9},
                    ARTICLE-NUMBER = {2165},
                    URL = {https://www.mdpi.com/1420-3049/25/9/2165},
                    ABSTRACT = {In view ... in MDF fractionation.},
                    DOI = {10.3390/molecules25092165}
                }
                """,
            },
        )

        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(citation_key="Hagel & Saake 2020")
        self.assertEqual(response.url, source.get_absolute_url())
        self.assertEqual(source.type, "article")
        self.assertEqual(source.title, "Fractionation of Waste MDF by Steam Refining")
        self.assertEqual(source.journal, "Molecules")
        self.assertEqual(source.volume, "25")
        self.assertEqual(source.number, "9")
        self.assertEqual(source.eid, "2165")
        self.assertIsNone(source.pages)
        self.assertEqual(
            list(
                source.sourceauthors.order_by("position").values_list(
                    "author_id",
                    flat=True,
                )
            ),
            [sebastian.pk, bodo.pk],
        )
