from django.test import TestCase

from ..bibtex import BibtexArticleParseError, parse_bibtex_article_entry


class ParseBibtexArticleNormalizationTestCase(TestCase):
    def test_parses_corporate_and_particle_authors_best_effort(self):
        entry = """
        @article{Corporate2024,
            author = {{World Health Organization} and de la Cruz, Juan and Ludwig van Beethoven},
            title = {Structured Authors},
            journal = {Metadata Quarterly},
            year = {2024}
        }
        """

        parsed = parse_bibtex_article_entry(entry)

        self.assertEqual(
            parsed["authors"],
            [
                {
                    "first_names": "",
                    "last_names": "World Health Organization",
                    "suffix": "",
                },
                {
                    "first_names": "Juan",
                    "last_names": "de la Cruz",
                    "suffix": "",
                },
                {
                    "first_names": "Ludwig",
                    "last_names": "van Beethoven",
                    "suffix": "",
                },
            ],
        )

    def test_rejects_duplicate_normalized_number_fields(self):
        with self.assertRaisesMessage(
            BibtexArticleParseError,
            "Duplicate BibTeX field 'number'.",
        ):
            parse_bibtex_article_entry(
                """
                @article{DuplicateIssue2024,
                    author = {Doe, Jane},
                    title = {Duplicate Fields},
                    journal = {Parser Journal},
                    year = {2024},
                    number = {2},
                    issue = {3}
                }
                """
            )

    def test_rejects_invalid_biblatex_date_format(self):
        with self.assertRaisesMessage(
            BibtexArticleParseError,
            "BibTeX date must use YYYY, YYYY-MM, or YYYY-MM-DD.",
        ):
            parse_bibtex_article_entry(
                """
                @article{InvalidDate2024,
                    author = {Doe, Jane},
                    title = {Date Parsing},
                    journal = {Parser Journal},
                    date = {2024-Spring}
                }
                """
            )
