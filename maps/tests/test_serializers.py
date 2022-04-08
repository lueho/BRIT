from django.test import TestCase, modify_settings

from users.models import get_default_owner
from ..models import NutsRegion
from ..serializers import NutsRegionSummarySerializer


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class NutsRegionSummarySerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        NutsRegion.objects.create(
            owner=owner,
            nuts_id='TE57',
            name_latn='Test NUTS'
        )

    def setUp(self):
        self.region = NutsRegion.objects.get(nuts_id='TE57')

    def test_serializer(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('nuts_id', data)
        self.assertIn('name', data)
