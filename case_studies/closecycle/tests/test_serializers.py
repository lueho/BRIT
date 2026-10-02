from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from case_studies.closecycle.models import Showcase
from case_studies.closecycle.serializers import ShowcaseFlatSerializer
from maps.models import Region
from processes.models import Process


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

    def test_involved_processes_returns_linked_process_chain(self):
        process = Process.objects.create(
            name="Linked Process", publication_status="published"
        )
        self.showcase.showcase_processes.create(process=process, order=1)
        permission = Permission.objects.get(codename="access_app_feature")
        self.user.user_permissions.add(permission)
        serializer = ShowcaseFlatSerializer(self.showcase)
        serializer.request = SimpleNamespace(user=self.user)
        data = serializer.data
        self.assertEqual(
            data["involved_processes"],
            [
                {
                    "name": "Linked Process",
                    "id": process.pk,
                    "url": f"/processes/types/{process.pk}/",
                }
            ],
        )

    def test_involved_processes_empty_for_user_without_permission(self):
        process = Process.objects.create(
            name="Linked Process", publication_status="published"
        )
        self.showcase.showcase_processes.create(process=process, order=1)
        user = get_user_model().objects.create(username="no_perm")
        serializer = ShowcaseFlatSerializer(self.showcase)
        serializer.request = SimpleNamespace(user=user)
        data = serializer.data
        self.assertEqual(data["involved_processes"], [])
