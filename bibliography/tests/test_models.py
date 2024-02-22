from django.test import TestCase

from ..models import Author


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
