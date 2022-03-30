from django.test import TestCase

from users.models import get_default_owner
from ..models import Source
from ..serializers import SourceAbbreviationSerializer


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
