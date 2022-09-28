from django.test import TestCase, RequestFactory
from django.urls import reverse

from users.models import get_default_owner

from ..filters import SourceFilter
from ..models import Author, Licence, Source

class SourceFilterTestCase(TestCase):

    author1 = None
    source = None


    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        cls.author1 = Author.objects.create(owner=owner, first_names='One', last_names='Test Author')
        author2 = Author.objects.create(owner=owner, first_names='Two', last_names='Test Author')
        licence = Licence.objects.create(owner=owner, name='Test Licence', reference_url='https://www.test-licence.org')
        cls.source = Source.objects.create(
            owner=owner,
            type='custom',
            title='Test Custom Source',
            abbreviation='TS1',
            licence=licence,
        )
        cls.source.authors.add(cls.author1)
        cls.source.authors.add(author2)
        source = Source.objects.create(
            owner=owner,
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
        self.assertQuerysetEqual(qs.order_by('id'), Source.objects.order_by('id'))

    def test_author_icontains_finds_first_names(self):
        factory = RequestFactory()
        filter_params = {
            'authors': 'One'
        }
        request = factory.get(reverse('source-detail', kwargs={'pk': self.source.pk}), filter_params)
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())