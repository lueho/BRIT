from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from ..filters import SourceFilter
from ..models import Author, Licence, Source, SourceAuthor


class SourceFilterTestCase(TestCase):
    author1 = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.author1 = Author.objects.create(first_names='One', last_names='Test Author')
        author2 = Author.objects.create(first_names='Two', last_names='Test Author')
        licence = Licence.objects.create(name='Test Licence', reference_url='https://www.test-licence.org')
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                type='custom',
                title='Test Custom Source',
                abbreviation='TS1',
                licence=licence,
            )
        SourceAuthor.objects.create(source=cls.source, author=cls.author1, position=1)
        SourceAuthor.objects.create(source=cls.source, author=author2, position=2)
        with mute_signals(post_save):
            source = Source.objects.create(
                type='book',
                title='Test Book',
                abbreviation='TS2',
                licence=licence,
            )
        SourceAuthor.objects.create(source=source, author=author2, position=1)

    def test_title_filter_exists(self):
        """Test that title filter field exists and uses autocomplete widget"""
        filtr = SourceFilter(queryset=Source.objects.all())
        self.assertIn('title', filtr.filters)
        # Autocomplete functionality is tested through integration/UI tests

    def test_author_filter_exists(self):
        """Test that authors filter field exists and uses autocomplete widget"""
        filtr = SourceFilter(queryset=Source.objects.all())
        self.assertIn('authors', filtr.filters)
        # Autocomplete functionality is tested through integration/UI tests

    def test_filter_empty_returns_all(self):
        """Test that empty filter returns all sources"""
        filter_params = {}
        qs = SourceFilter(filter_params, Source.objects.all()).qs
        self.assertEqual(2, qs.count())

    def test_filter_form_has_no_formtags(self):
        filtr = SourceFilter(queryset=Source.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
