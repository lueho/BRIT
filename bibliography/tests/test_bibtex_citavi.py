from django.test import TestCase

from utils.object_management.models import User

from ..bibtex import parse_bibtex_article_entry
from ..forms import SourceBibtexArticleImportForm
from ..models import Author


class ParseBibtexCitaviEntryTestCase(TestCase):
    def test_parses_citavi_biblatex_field_aliases(self):
        entry = """
        @article{Doe2024,
            author = {Doe, Jane},
            title = {Citavi Export Compatibility Test},
            journaltitle = {Journal of Circular Systems},
            date = {2024-03-15},
            volume = {12},
            issue = {2},
            eid = {e145},
            url = {https://example.com/citavi-entry},
            abstract = {Citavi-style BibLaTeX export example.}
        }
        """

        parsed = parse_bibtex_article_entry(entry)

        self.assertEqual(parsed["citation_key"], "Doe2024")
        self.assertEqual(parsed["journal"], "Journal of Circular Systems")
        self.assertEqual(parsed["year"], 2024)
        self.assertEqual(parsed["month"], "mar")
        self.assertEqual(parsed["volume"], "12")
        self.assertEqual(parsed["number"], "2")
        self.assertEqual(parsed["eid"], "e145")
        self.assertEqual(parsed["url"], "https://example.com/citavi-entry")
        self.assertEqual(
            parsed["authors"],
            [
                {"first_names": "Jane", "last_names": "Doe", "suffix": ""},
            ],
        )


class SourceBibtexCitaviImportFormTestCase(TestCase):
    def test_form_creates_article_source_from_citavi_style_fields(self):
        owner = User.objects.create(username="owner")
        jane = Author.objects.create(
            owner=owner,
            first_names="Jane",
            last_names="Doe",
        )
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": """
                @article{Doe2024,
                    author = {Doe, Jane},
                    title = {Citavi Export Compatibility Test},
                    journaltitle = {Journal of Circular Systems},
                    date = {2024-03-15},
                    volume = {12},
                    issue = {2},
                    eid = {e145}
                }
                """,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        source = form.create_source(owner=owner)

        self.assertEqual(source.citation_key, "Doe 2024")
        self.assertEqual(source.title, "Citavi Export Compatibility Test")
        self.assertEqual(source.journal, "Journal of Circular Systems")
        self.assertEqual(source.volume, "12")
        self.assertEqual(source.number, "2")
        self.assertEqual(source.eid, "e145")
        self.assertEqual(source.month, "mar")
        self.assertEqual(source.year, 2024)
        self.assertIsNone(source.pages)
        self.assertEqual(source.sourceauthors.get().author_id, jane.pk)
