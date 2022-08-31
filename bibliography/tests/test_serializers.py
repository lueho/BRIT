from collections import OrderedDict
from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse

from users.models import get_default_owner
from ..models import Author, Licence, Source
from ..serializers import (HyperlinkedAuthorSerializer, HyperlinkedSourceSerializer, HyperlinkedLicenceSerializer,
                           SourceAbbreviationSerializer)


class HyperlinkedLicenceSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        cls.licence = Licence.objects.create(owner=owner, name='Test Licence', reference_url='https://www.licence.com')

    def test_data_rep(self):
        request = RequestFactory().get(reverse('licence-detail', kwargs={'pk': self.licence.pk}))
        serializer = HyperlinkedLicenceSerializer(self.licence, context={'request': request})
        expected = {
            'name': self.licence.name,
            'url': request.build_absolute_uri()
        }
        self.assertDictEqual(expected, dict(serializer.data))


class HyperlinkedAuthorSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        cls.author = Author.objects.create(owner=owner, first_names='Test', last_names='author')

    def test_data_rep(self):
        request = RequestFactory().get(reverse('author-detail', kwargs={'pk': self.author.pk}))
        serializer = HyperlinkedAuthorSerializer(self.author, context={'request': request})
        expected = {
            'name': f'{self.author.last_names}, {self.author.first_names}',
            'url': request.build_absolute_uri()
        }
        self.assertDictEqual(expected, dict(serializer.data))


class HyperlinkedSourceSerializerTestCase(TestCase):
    author1 = None
    author2 = None

    @classmethod
    def setUpTestData(cls):
        cls.maxDiff = None
        owner = get_default_owner()
        cls.author1 = Author.objects.create(owner=owner, first_names='One', last_names='Test Author')
        cls.author2 = Author.objects.create(owner=owner, first_names='Two', last_names='Test Author')
        licence = Licence.objects.create(owner=owner, name='Test Licence', reference_url='https://www.licence.com')
        source = Source.objects.create(
            owner=owner,
            type='custom',
            title='Test Source',
            abbreviation='TS1',
            licence=licence,
            publisher='Test Publisher',
            journal='Test Journal',
            issue='Test Issue',
            year=2022,
            abstract='Test Abstract',
            attributions='Test Attributions',
            url='https://www.test_url.org',
            url_valid=True,
            url_checked=date.today(),
            doi='10.1000/282',
            last_accessed=date.today()
        )
        source.authors.set([cls.author1, cls.author2])
        cls.source = source

    def test_data_rep(self):
        factory = RequestFactory()
        request = factory.get(reverse('home'))
        serializer = HyperlinkedSourceSerializer(self.source, context={'request': request})

        expected = {
            'abbreviation': 'TS1',
            'authors': [
                OrderedDict([('name', 'Test Author, One'),
                             ('url',
                              factory.get(
                                  reverse('author-detail', kwargs={'pk': self.author1.pk})).build_absolute_uri())]),
                OrderedDict([('name', 'Test Author, Two'),
                             ('url',
                              factory.get(
                                  reverse('author-detail', kwargs={'pk': self.author2.pk})).build_absolute_uri())])
            ],
            'title': self.source.title,
            'type': self.source.type,
            'licence': OrderedDict([
                    ('name', 'Test Licence'),
                    ('url',
                     factory.get(reverse('licence-detail', kwargs={'pk': self.source.licence.pk})).build_absolute_uri())
                ]),
            'publisher': self.source.publisher,
            'journal': self.source.journal,
            'issue': self.source.issue,
            'year': self.source.year,
            'abstract': self.source.abstract,
            'attributions': self.source.attributions,
            'url': self.source.url,
            'url_valid': self.source.url_valid,
            'url_checked': self.source.url_checked.strftime('%d.%m.%Y'),
            'doi': OrderedDict([('name', self.source.doi), ('url', f'https://doi.org/{self.source.doi}')]),
            'last_accessed': self.source.last_accessed.strftime('%d.%m.%Y')
        }
        self.assertDictEqual(expected, serializer.data)


class SourceAbbreviationSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        Source.objects.create(owner=owner, title='Test Source', abbreviation='(TS, 1955)')

    def setUp(self):
        self.source = Source.objects.get(title='Test Source')

    def test_source_link_serializer(self):
        data = SourceAbbreviationSerializer(self.source).data
        self.assertIn('pk', data)
        self.assertIn('abbreviation', data)
