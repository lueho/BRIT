from django.test import TestCase
from mock import patch, Mock

from users.models import get_default_owner
from ..models import Source


class WebSourceTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='WORKING',
            url='https://httpbin.org/status/200'
        )
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='OUTDATED',
            url='https://httpbin.org/status/404'
        )
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='NOURL',
        )

    def setUp(self):
        self.working_source = Source.objects.get(abbreviation='WORKING')
        self.outdated_source = Source.objects.get(abbreviation='OUTDATED')
        self.no_url_source = Source.objects.get(abbreviation='NOURL')

    def test_check_url_returns_true_for_valid_url(self):
        self.assertTrue(self.working_source.check_url())

    def test_check_returns_false_for_invalid_url(self):
        self.assertFalse(self.outdated_source.check_url())

    def test_check_url_returns_false_for_source_without_url(self):
        self.assertFalse(self.no_url_source.check_url())

    def test_url_valid_is_checked_and_set_to_true_on_creation_for_valid_urls(self):
        source = Source.objects.create(
            owner=get_default_owner(),
            title='Test Source from the Web',
            abbreviation='NEWANDWORKING',
            url='https://httpbin.org/status/200'
        )
        self.assertTrue(source.url_valid)
