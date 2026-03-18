from django.test import TestCase

from ..bibtex import (
    BibtexArticleParseError,
    parse_bibtex_article_entry,
)


class ParseBibtexArticleEntryTestCase(TestCase):
    def test_parses_supported_article_fields(self):
        entry = """
        @article{Lovelace1843,
            author = {Lovelace, Ada and Hopper, Grace},
            title = {Notes on the Analytical Engine},
            journal = {Scientific Memoirs},
            year = {1843},
            volume = {3},
            number = {4},
            pages = {666--699},
            month = {Dec},
            doi = {10.1000/test-doi},
            url = {https://example.com/article},
            abstract = {Annotated translation.}
        }
        """

        parsed = parse_bibtex_article_entry(entry)

        self.assertEqual(parsed["entry_type"], "article")
        self.assertEqual(parsed["citation_key"], "Lovelace1843")
        self.assertEqual(parsed["title"], "Notes on the Analytical Engine")
        self.assertEqual(parsed["journal"], "Scientific Memoirs")
        self.assertEqual(parsed["year"], 1843)
        self.assertEqual(parsed["volume"], "3")
        self.assertEqual(parsed["number"], "4")
        self.assertEqual(parsed["pages"], "666-699")
        self.assertEqual(parsed["month"], "dec")
        self.assertEqual(parsed["doi"], "10.1000/test-doi")
        self.assertEqual(parsed["url"], "https://example.com/article")
        self.assertEqual(parsed["abstract"], "Annotated translation.")
        self.assertEqual(
            parsed["authors"],
            [
                {"first_names": "Ada", "last_names": "Lovelace", "suffix": ""},
                {"first_names": "Grace", "last_names": "Hopper", "suffix": ""},
            ],
        )

    def test_rejects_non_article_entries(self):
        with self.assertRaisesMessage(
            BibtexArticleParseError,
            "Only BibTeX @article entries are supported.",
        ):
            parse_bibtex_article_entry(
                "@book{Lovelace1843, title={Notes}, year={1843}}"
            )
