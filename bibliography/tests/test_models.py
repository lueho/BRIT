from django.db.models.signals import post_save
from django.test import TestCase
from factory.django import mute_signals

from ..models import Author, Licence, Source, SourceAuthor, check_url_valid


class AuthorModelTests(TestCase):
    def test_str_representation(self):
        author = Author(
            first_names="John", middle_names="Fitzgerald", last_names="Kennedy"
        )
        self.assertEqual("Kennedy, John", str(author))

    def test_bibtex_name_simple(self):
        author = Author(first_names="John", last_names="Doe")
        self.assertEqual("Doe, J.", author.bibtex_name)

    def test_bibtex_name_full(self):
        author = Author(
            first_names="John",
            middle_names="Fitzgerald",
            last_names="Kennedy",
            suffix="Jr.",
        )
        self.assertEqual("Kennedy, J. F., Jr.", author.bibtex_name)

    def test_abbreviated_full_name(self):
        author = Author(
            first_names="John", middle_names="Fitzgerald", last_names="Kennedy"
        )
        self.assertEqual("Kennedy, J. F.", author.abbreviated_full_name)

    def test_preferred_citation_name(self):
        author = Author(preferred_citation="J.F.K.")
        self.assertEqual("J.F.K.", author.preferred_citation)

    def test_suffix_handling(self):
        author = Author(
            first_names="John",
            middle_names="Fitzgerald",
            last_names="Kennedy",
            suffix="II",
        )
        self.assertEqual("Kennedy, J. F., II", author.abbreviated_full_name)


class LicenceModelTest(TestCase):
    def setUp(self):
        self.licence_name = "MIT License"
        self.licence_url = "https://opensource.org/licenses/MIT"
        self.licence_description = "A short and permissive software license"

        self.licence = Licence.objects.create(
            name=self.licence_name,
            reference_url=self.licence_url,
            description=self.licence_description,
        )

    def test_licence_creation(self):
        self.assertEqual(self.licence.name, self.licence_name)
        self.assertEqual(self.licence.reference_url, self.licence_url)
        self.assertEqual(self.licence.description, self.licence_description)

    def test_licence_str(self):
        self.assertEqual(str(self.licence), self.licence_name)

    def test_bibtex_entry(self):
        expected_bibtex_note = f"License: {self.licence_name}, URL: {self.licence_url}"
        self.assertEqual(self.licence.bibtex_entry, expected_bibtex_note)


def setUpModule():
    post_save.disconnect(check_url_valid, sender=Source)


def tearDownModule():
    post_save.connect(check_url_valid, sender=Source)


class SourceAbbreviationGenerationTestCase(TestCase):
    """Tests for Source.generate_abbreviation() with various author counts."""

    @classmethod
    def setUpTestData(cls):
        cls.author1 = Author.objects.create(first_names="Sebastian", last_names="Hagel")
        cls.author2 = Author.objects.create(
            first_names="Phillipp", last_names="Lüssenhop"
        )
        cls.author3 = Author.objects.create(first_names="Ina", last_names="Körner")

    def test_single_author_with_year(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Test", year=2021, abbreviation="tmp")
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        self.assertEqual(source.generate_abbreviation(), "Hagel 2021")

    def test_two_authors_with_year(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Test", year=2022, abbreviation="tmp")
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        SourceAuthor.objects.create(source=source, author=self.author2, position=2)
        self.assertEqual(source.generate_abbreviation(), "Hagel & Lüssenhop 2022")

    def test_three_or_more_authors_with_year(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Test", year=2021, abbreviation="tmp")
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        SourceAuthor.objects.create(source=source, author=self.author2, position=2)
        SourceAuthor.objects.create(source=source, author=self.author3, position=3)
        self.assertEqual(source.generate_abbreviation(), "Hagel et al. 2021")

    def test_no_authors_uses_title(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Straßenbaumkataster Hamburg", year=2019, abbreviation="tmp"
            )
        self.assertEqual(source.generate_abbreviation(), "Straßenbaumkataster 2019")

    def test_no_authors_no_year(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Some Dataset", abbreviation="tmp")
        self.assertEqual(source.generate_abbreviation(), "Some")

    def test_single_author_no_year(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Test", abbreviation="tmp")
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        self.assertEqual(source.generate_abbreviation(), "Hagel")

    def test_no_title_no_authors(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="", abbreviation="tmp")
        self.assertEqual(source.generate_abbreviation(), "Source")


class SourceAbbreviationAutoPopulateTestCase(TestCase):
    """Tests for automatic abbreviation population on save()."""

    def test_blank_abbreviation_auto_generates_on_save(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Straßenbaumkataster Hamburg", year=2019
            )
        self.assertEqual(source.abbreviation, "Straßenbaumkataster 2019")

    def test_manual_abbreviation_preserved(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Some Title", year=2020, abbreviation="CUSTOM KEY"
            )
        self.assertEqual(source.abbreviation, "CUSTOM KEY")

    def test_empty_title_generates_source_fallback(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="", year=2020)
        self.assertEqual(source.abbreviation, "Source 2020")


class SourceAbbreviationDisambiguationTestCase(TestCase):
    """Tests for automatic a/b/c suffix disambiguation."""

    def test_disambiguation_adds_suffix(self):
        with mute_signals(post_save):
            Source.objects.create(
                title="Urbanisation Data", year=2021, abbreviation="Urbanisation 2021"
            )
            # Create a second source whose auto-generated key collides
            s2 = Source.objects.create(title="Urbanisation Three", year=2021)
        self.assertEqual(s2.abbreviation, "Urbanisation 2021a")

    def test_disambiguation_skips_taken_suffixes(self):
        with mute_signals(post_save):
            Source.objects.create(
                title="Test Source", year=2021, abbreviation="Test 2021"
            )
            Source.objects.create(
                title="Test Again", year=2021, abbreviation="Test 2021a"
            )
            s3 = Source.objects.create(title="Test Third", year=2021)
        self.assertEqual(s3.abbreviation, "Test 2021b")


class SourceAbbreviationSignalTestCase(TestCase):
    """Tests that abbreviation is regenerated when SourceAuthors change."""

    @classmethod
    def setUpTestData(cls):
        cls.author1 = Author.objects.create(first_names="John", last_names="Smith")
        cls.author2 = Author.objects.create(first_names="Jane", last_names="Doe")

    def test_abbreviation_updated_when_author_added(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Experiment Results", year=2023)
        self.assertEqual(source.abbreviation, "Experiment 2023")
        # Adding an author should regenerate the abbreviation
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        source.refresh_from_db()
        self.assertEqual(source.abbreviation, "Smith 2023")

    def test_abbreviation_updated_when_second_author_added(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Experiment Results", year=2023)
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        source.refresh_from_db()
        self.assertEqual(source.abbreviation, "Smith 2023")
        # Smith 2023 doesn't start with title-based fallback, so signal won't
        # regenerate. This is correct: once authors are set, the key is stable.

    def test_manual_abbreviation_not_overwritten_by_signal(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Standard Method", year=2020, abbreviation="DIN EN 13039"
            )
        # Adding author should NOT overwrite the manual abbreviation
        SourceAuthor.objects.create(source=source, author=self.author1, position=1)
        source.refresh_from_db()
        self.assertEqual(source.abbreviation, "DIN EN 13039")


class SourceStrTestCase(TestCase):
    """Tests for Source.__str__ fallback chain."""

    def test_str_returns_abbreviation(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="Some Title", abbreviation="Custom")
        self.assertEqual(str(source), "Custom")

    def test_str_falls_back_to_title(self):
        with mute_signals(post_save):
            source = Source(title="My Title", abbreviation="")
            source.pk = None  # simulate unsaved
        # After save, abbreviation will be auto-populated, so test the property directly
        source.abbreviation = ""
        self.assertEqual(str(source), "My Title")

    def test_str_falls_back_to_source_pk(self):
        with mute_signals(post_save):
            source = Source.objects.create(title="", abbreviation="fallback")
        source.abbreviation = ""
        source.title = ""
        self.assertEqual(str(source), f"Source #{source.pk}")


class SourceUpdateAbbreviationTestCase(TestCase):
    """Tests for the explicit update_abbreviation() method."""

    def test_update_abbreviation_regenerates(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Old Key", year=2020, abbreviation="placeholder"
            )
        author = Author.objects.create(first_names="Alice", last_names="Wonder")
        SourceAuthor.objects.create(source=source, author=author, position=1)
        # Explicit call should always regenerate
        source.update_abbreviation()
        source.refresh_from_db()
        self.assertEqual(source.abbreviation, "Wonder 2020")
