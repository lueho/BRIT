from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from ..filters import SourceFilter
from ..models import Author, Licence, Source


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
        cls.source.authors.add(cls.author1)
        cls.source.authors.add(author2)
        with mute_signals(post_save):
            source = Source.objects.create(
                type='book',
                title='Test Book',
                abbreviation='TS2',
                licence=licence,
            )
        source.authors.add(author2)

    def test_title_icontains(self):
        factory = RequestFactory()
        filter_params = {
            'title': 'Custom'
        }
        request = factory.get(reverse('source-detail', kwargs={'pk': self.source.pk}), filter_params)
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual('Test Custom Source', qs.first().title)

    def test_author_icontains_finds_last_names(self):
        factory = RequestFactory()
        filter_params = {
            'authors': 'Test'
        }
        request = factory.get(reverse('source-detail', kwargs={'pk': self.source.pk}), filter_params)
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(2, qs.count())
        self.assertQuerySetEqual(qs.order_by('id'), Source.objects.order_by('id'))

    def test_author_icontains_finds_first_names(self):
        factory = RequestFactory()
        filter_params = {
            'authors': 'One'
        }
        request = factory.get(reverse('source-detail', kwargs={'pk': self.source.pk}), filter_params)
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())

    def test_filter_form_has_no_formtags(self):
        filtr = SourceFilter(queryset=Source.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
