from django.contrib.auth import get_user_model
from django.test import TestCase

from case_studies.closecycle.models import Showcase
from case_studies.closecycle.serializers import ShowcaseFlatSerializer
from maps.models import Region


class ShowcaseFlatSerializerRegressionTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username="dummy", is_staff=True)
        self.region = Region.objects.create(name="Test Region")
        self.showcase = Showcase.objects.create(
            name="Test Showcase", region_id=self.region.id
        )

    def test_showcase_flat_serializer_works_without_request(self):
        """
        Regression test: ShowcaseFlatSerializer should work without a request context.
        involved_processes should be an empty list if no request/user is present.
        """
        serializer = ShowcaseFlatSerializer(self.showcase)
        data = serializer.data
        self.assertIn("involved_processes", data)
        self.assertEqual(data["involved_processes"], [])
