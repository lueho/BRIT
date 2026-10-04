from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from case_studies.closecycle.models import Showcase
from case_studies.closecycle.serializers import (
    ShowcaseFlatSerializer,
    ShowcaseModelSerializer,
)
from maps.models import Region
from materials.models import Material, Sample
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


class ShowcaseModelSerializerConnectionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create(username="private_owner")
        region = Region.objects.create(name="API Region")
        cls.showcase = Showcase.objects.create(
            name="API Showcase", region=region, publication_status="published"
        )
        public_material = Material.objects.create(
            name="Public Feedstock", publication_status="published"
        )
        private_material = Material.objects.create(
            name="Private Feedstock", owner=cls.owner
        )
        for material in (public_material, private_material):
            cls.showcase.showcase_materials.create(material=material, role="input")
        public_process = Process.objects.create(
            name="Public Step", publication_status="published"
        )
        private_process = Process.objects.create(name="Private Step", owner=cls.owner)
        for order, process in enumerate((public_process, private_process)):
            cls.showcase.showcase_processes.create(process=process, order=order)
        cls.showcase.samples.add(
            Sample.objects.create(
                name="Private Sample", material=public_material, owner=cls.owner
            )
        )

    def test_connection_fields_are_read_only(self):
        fields = ShowcaseModelSerializer().fields
        for name in (
            "catchment",
            "showcase_materials",
            "process_chain",
            "samples",
            "sample_series",
            "scenarios",
        ):
            with self.subTest(field=name):
                self.assertTrue(fields[name].read_only)

    def test_anonymous_api_detail_hides_private_connections(self):
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.showcase.pk])
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(
            ["Public Feedstock"],
            [link["material"] for link in data["showcase_materials"]],
        )
        self.assertEqual(
            ["Public Step"], [step["name"] for step in data["process_chain"]]
        )
        self.assertEqual([], data["samples"])

    def test_owner_api_detail_includes_own_private_connections(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.showcase.pk])
        )
        data = response.json()
        self.assertEqual(
            ["Public Feedstock", "Private Feedstock"],
            [link["material"] for link in data["showcase_materials"]],
        )
        self.assertEqual(
            ["Public Step", "Private Step"],
            [step["name"] for step in data["process_chain"]],
        )
        self.assertEqual(["Private Sample"], [s["name"] for s in data["samples"]])

    def test_involved_processes_hide_private_processes(self):
        user = get_user_model().objects.create(username="feature_user")
        user.user_permissions.add(Permission.objects.get(codename="access_app_feature"))
        serializer = ShowcaseFlatSerializer(self.showcase)
        serializer.request = SimpleNamespace(user=user)
        self.assertEqual(
            ["Public Step"],
            [proc["name"] for proc in serializer.data["involved_processes"]],
        )


class ShowcaseMapEndpointPrefetchTest(TestCase):
    CONNECTION_TABLES = (
        "closecycle_showcasematerial",
        "closecycle_showcaseprocess",
        "materials_sample",
        "materials_sampleseries",
        "maps_catchment",
        "inventories_scenario",
    )

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name="Map Region")
        cls.showcase = Showcase.objects.create(
            name="Map Showcase", region=region, publication_status="published"
        )
        material = Material.objects.create(
            name="Map Feedstock", publication_status="published"
        )
        cls.showcase.showcase_materials.create(material=material, role="input")
        process = Process.objects.create(
            name="Map Step", publication_status="published"
        )
        cls.showcase.showcase_processes.create(process=process, order=0)

    def _queried_connection_tables(self, url_name):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse(url_name), {"id": self.showcase.pk})
        self.assertEqual(200, response.status_code)
        sql = " ".join(query["sql"] for query in queries.captured_queries)
        return {table for table in self.CONNECTION_TABLES if f'"{table}"' in sql}

    def test_geojson_does_not_load_connections(self):
        self.assertEqual(set(), self._queried_connection_tables("api-showcase-geojson"))

    def test_summaries_load_only_process_links(self):
        self.assertEqual(
            {"closecycle_showcaseprocess"},
            self._queried_connection_tables("api-showcase-summaries"),
        )
