from django.test import TestCase

from utils.object_management.models import User

from ..models import SOURCE_TYPE_MAPPINGS, SOURCE_TYPES, Source

EXPECTED_TYPE_KEYS = {
    "article",
    "book",
    "incollection",
    "proceedings",
    "inproceedings",
    "report",
    "thesis",
    "dataset",
    "standard",
    "patent",
    "online",
    "periodical",
    "preprint",
    "misc",
}

MAPPING_VOCABULARIES = {"bibtex", "biblatex", "csl", "zotero", "ris", "crossref"}


class SourceTypeVocabularyTestCase(TestCase):
    """The source type vocabulary must stay interoperable with BibTeX,
    biblatex, RIS, CSL/Zotero, and CrossRef."""

    def test_source_types_cover_expected_bibliographic_vocabulary(self):
        self.assertEqual({key for key, _ in SOURCE_TYPES}, EXPECTED_TYPE_KEYS)

    def test_source_type_labels_are_human_readable(self):
        for key, label in SOURCE_TYPES:
            self.assertTrue(label.strip(), f"Missing label for type '{key}'")
            self.assertNotEqual(key, label)

    def test_every_type_has_complete_external_mappings(self):
        for key, _ in SOURCE_TYPES:
            with self.subTest(type=key):
                self.assertIn(key, SOURCE_TYPE_MAPPINGS)
                mapping = SOURCE_TYPE_MAPPINGS[key]
                self.assertEqual(set(mapping), MAPPING_VOCABULARIES)
                for vocabulary, value in mapping.items():
                    self.assertTrue(
                        value,
                        f"Missing {vocabulary} mapping for type '{key}'",
                    )

    def test_bibtex_and_biblatex_keys_are_lowercase_bibtex_identifiers(self):
        for key, mapping in SOURCE_TYPE_MAPPINGS.items():
            with self.subTest(type=key):
                self.assertRegex(mapping["bibtex"], r"^[a-z]+$")
                self.assertRegex(mapping["biblatex"], r"^[a-z]+$")

    def test_internal_waste_flyer_type_is_not_part_of_the_vocabulary(self):
        self.assertNotIn("waste_flyer", {key for key, _ in SOURCE_TYPES})

    def test_default_type_is_misc(self):
        source = Source(title="Some record")
        self.assertEqual(source.type, "misc")

    def test_get_or_create_misc_by_title_uses_misc_type(self):
        owner = User.objects.create(username="owner")
        source, created = Source.objects.get_or_create_misc_by_title(
            owner=owner, title="Grey literature note"
        )
        self.assertTrue(created)
        self.assertEqual(source.type, "misc")

        same_source, created_again = Source.objects.get_or_create_misc_by_title(
            owner=owner, title="Grey literature note"
        )
        self.assertFalse(created_again)
        self.assertEqual(same_source.pk, source.pk)
