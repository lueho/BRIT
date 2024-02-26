from django.test import TestCase

from ..models import Author, Licence


class AuthorModelTests(TestCase):
    def test_str_representation(self):
        author = Author(first_names="John", middle_names="Fitzgerald", last_names="Kennedy")
        self.assertEqual("Kennedy, John", str(author))

    def test_bibtex_name_simple(self):
        author = Author(first_names="John", last_names="Doe")
        self.assertEqual("Doe, J.", author.bibtex_name)

    def test_bibtex_name_full(self):
        author = Author(first_names="John", middle_names="Fitzgerald", last_names="Kennedy", suffix="Jr.")
        self.assertEqual("Kennedy, J. F., Jr.", author.bibtex_name)

    def test_abbreviated_full_name(self):
        author = Author(first_names="John", middle_names="Fitzgerald", last_names="Kennedy")
        self.assertEqual("Kennedy, J. F.", author.abbreviated_full_name)

    def test_preferred_citation_name(self):
        author = Author(preferred_citation="J.F.K.")
        self.assertEqual("J.F.K.", author.preferred_citation)

    def test_suffix_handling(self):
        author = Author(first_names="John", middle_names="Fitzgerald", last_names="Kennedy", suffix="II")
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
