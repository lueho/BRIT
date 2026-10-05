from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from case_studies.closecycle.models import Showcase
from case_studies.closecycle.serializers import (
    ShowcaseFlatSerializer,
    ShowcaseGeoFeatureModelSerializer,
    ShowcaseModelSerializer,
)
from maps.models import Region
from materials.models import Material, Sample
from processes.models import Process


def _context(user=None):
    return {"request": SimpleNamespace(user=user or AnonymousUser())}


class ShowcaseFlatSerializerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create(username="connection_owner")
        cls.other_user = User.objects.create(username="unrelated_user")
        cls.region = Region.objects.create(name="Test Region")
        cls.showcase = Showcase.objects.create(
            name="Test Showcase",
            region=cls.region,
            publication_status="published",
        )
        cls.input_material = Material.objects.create(
            name="Input Feedstock", publication_status="published"
        )
        cls.intermediate_material = Material.objects.create(
            name="Intermediate Feedstock", publication_status="published"
        )
        cls.product_material = Material.objects.create(
            name="Product Feedstock", publication_status="published"
        )
        cls.private_material = Material.objects.create(
            name="Private Feedstock", owner=cls.owner
        )
        cls.showcase.showcase_materials.create(
            material=cls.input_material, role="input", order=0
        )
        cls.showcase.showcase_materials.create(
            material=cls.intermediate_material, role="intermediate", order=0
        )
        cls.showcase.showcase_materials.create(
            material=cls.product_material, role="product", order=0
        )
        cls.showcase.showcase_materials.create(
            material=cls.private_material, role="input", order=1
        )
        cls.showcase.showcase_materials.create(
            material=cls.input_material, role="product", order=1
        )
        cls.process_b = Process.objects.create(
            name="Zeta Step", publication_status="published"
        )
        cls.process_a = Process.objects.create(
            name="Alpha Step", publication_status="published"
        )
        cls.private_process = Process.objects.create(
            name="Private Step", owner=cls.owner
        )
        cls.showcase.showcase_processes.create(process=cls.process_b, order=0)
        cls.showcase.showcase_processes.create(process=cls.process_a, order=1)
        cls.showcase.showcase_processes.create(process=cls.private_process, order=2)

    def test_works_without_request_context_as_anonymous(self):
        data = ShowcaseFlatSerializer(self.showcase).data
        self.assertEqual(
            ["Zeta Step", "Alpha Step"],
            [proc["name"] for proc in data["involved_processes"]],
        )

    def test_process_chain_follows_configured_order_not_alphabetical(self):
        data = ShowcaseFlatSerializer(self.showcase, context=_context()).data
        self.assertEqual(
            [
                {
                    "name": "Zeta Step",
                    "id": self.process_b.pk,
                    "url": reverse(
                        "processes:processtype-detail", args=[self.process_b.pk]
                    ),
                },
                {
                    "name": "Alpha Step",
                    "id": self.process_a.pk,
                    "url": reverse(
                        "processes:processtype-detail", args=[self.process_a.pk]
                    ),
                },
            ],
            data["involved_processes"],
        )

    def test_material_roles_are_grouped_and_ordered(self):
        data = ShowcaseFlatSerializer(self.showcase, context=_context()).data
        self.assertEqual(
            ["Input Feedstock"],
            [entry["name"] for entry in data["input_materials"]],
        )
        self.assertEqual(
            ["Intermediate Feedstock"],
            [entry["name"] for entry in data["intermediate_materials"]],
        )
        self.assertEqual(
            ["Product Feedstock", "Input Feedstock"],
            [entry["name"] for entry in data["products"]],
        )
        input_entry = data["input_materials"][0]
        self.assertEqual(
            {
                "id": self.input_material.pk,
                "name": "Input Feedstock",
                "url": reverse("material-detail", args=[self.input_material.pk]),
            },
            input_entry,
        )

    def test_private_connections_hidden_for_anonymous(self):
        data = ShowcaseFlatSerializer(self.showcase).data
        self.assertNotIn(
            "Private Feedstock",
            [entry["name"] for entry in data["input_materials"]],
        )
        self.assertNotIn(
            "Private Step",
            [proc["name"] for proc in data["involved_processes"]],
        )

    def test_private_connections_hidden_for_unrelated_user(self):
        data = ShowcaseFlatSerializer(
            self.showcase, context=_context(self.other_user)
        ).data
        self.assertNotIn(
            "Private Feedstock",
            [entry["name"] for entry in data["input_materials"]],
        )
        self.assertNotIn(
            "Private Step",
            [proc["name"] for proc in data["involved_processes"]],
        )

    def test_owner_sees_private_connections(self):
        data = ShowcaseFlatSerializer(self.showcase, context=_context(self.owner)).data
        self.assertIn(
            "Private Feedstock",
            [entry["name"] for entry in data["input_materials"]],
        )
        self.assertIn(
            "Private Step",
            [proc["name"] for proc in data["involved_processes"]],
        )

    def test_url_points_to_showcase_detail(self):
        data = ShowcaseFlatSerializer(self.showcase).data
        self.assertEqual(
            reverse("showcase-detail", args=[self.showcase.pk]), data["url"]
        )

    def test_missing_region_serializes_as_null(self):
        showcase = Showcase.objects.create(
            name="No Region", publication_status="published"
        )
        data = ShowcaseFlatSerializer(showcase).data
        self.assertIsNone(data["region"])

    def test_empty_connections_serialize_as_empty_lists(self):
        showcase = Showcase.objects.create(
            name="Empty Showcase", publication_status="published"
        )
        data = ShowcaseFlatSerializer(showcase).data
        self.assertEqual([], data["involved_processes"])
        self.assertEqual([], data["input_materials"])
        self.assertEqual([], data["intermediate_materials"])
        self.assertEqual([], data["products"])


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
        serializer = ShowcaseFlatSerializer(self.showcase, context=_context())
        self.assertEqual(
            ["Public Step"],
            [proc["name"] for proc in serializer.data["involved_processes"]],
        )


class ShowcaseGeoFeatureModelSerializerTest(TestCase):
    """A showcase is a location: its map geometry is its own site point,
    falling back to the centroid of the anchor region's borders."""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(
            name="Geo Region", publication_status="published"
        )
        cls.region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 2, 2)))
        cls.region.save()

    def _geometry(self, showcase):
        return ShowcaseGeoFeatureModelSerializer(showcase).data["geometry"]

    def test_serializes_own_site_point(self):
        showcase = Showcase.objects.create(
            name="Site Showcase",
            region=self.region,
            geom=Point(10.5, 52.3, srid=4326),
            publication_status="published",
        )
        self.assertEqual(
            {"type": "Point", "coordinates": [10.5, 52.3]},
            self._geometry(showcase),
        )

    def test_falls_back_to_region_centroid(self):
        showcase = Showcase.objects.create(
            name="Region Showcase",
            region=self.region,
            publication_status="published",
        )
        self.assertEqual(
            {"type": "Point", "coordinates": [1.0, 1.0]}, self._geometry(showcase)
        )

    def test_without_site_or_borders_geometry_is_null(self):
        showcase = Showcase.objects.create(
            name="Nowhere Showcase",
            region=Region.objects.create(name="Bald Region"),
            publication_status="published",
        )
        self.assertIsNone(self._geometry(showcase))


class ShowcaseSummariesEndpointTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name="Summary Region")
        cls.first = Showcase.objects.create(
            name="First Showcase", region=region, publication_status="published"
        )
        cls.second = Showcase.objects.create(
            name="Second Showcase", region=region, publication_status="published"
        )
        cls.private = Showcase.objects.create(
            name="Private Showcase",
            region=region,
            owner=get_user_model().objects.create(username="shy_owner"),
        )

    def test_summaries_returns_empty_list_without_matches(self):
        response = self.client.get(reverse("api-showcase-summaries"), {"id": 999999})
        self.assertEqual(200, response.status_code)
        self.assertEqual({"summaries": []}, response.json())

    def test_summaries_returns_all_matching_showcases(self):
        response = self.client.get(reverse("api-showcase-summaries"))
        self.assertEqual(200, response.status_code)
        data = response.json()
        names = [summary["name"] for summary in data["summaries"]]
        self.assertEqual(["First Showcase", "Second Showcase"], names)

    def test_summaries_can_be_filtered_by_id(self):
        response = self.client.get(
            reverse("api-showcase-summaries"), {"id": self.second.pk}
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data["summaries"]))
        self.assertEqual("Second Showcase", data["summaries"][0]["name"])

    def test_summaries_hides_private_showcases(self):
        response = self.client.get(reverse("api-showcase-summaries"))
        data = response.json()
        self.assertNotIn(
            "Private Showcase",
            [summary["name"] for summary in data["summaries"]],
        )
        response = self.client.get(
            reverse("api-showcase-summaries"), {"id": self.private.pk}
        )
        self.assertEqual({"summaries": []}, response.json())


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

    def test_summaries_load_only_material_and_process_links(self):
        self.assertEqual(
            {"closecycle_showcasematerial", "closecycle_showcaseprocess"},
            self._queried_connection_tables("api-showcase-summaries"),
        )

    def test_summaries_queries_do_not_grow_with_showcase_count(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse("api-showcase-summaries"))
            self.assertEqual(200, response.status_code)
            return len(queries.captured_queries)

        baseline = count_queries()
        for index in range(2):
            showcase = Showcase.objects.create(
                name=f"Extra Showcase {index}",
                region=self.showcase.region,
                publication_status="published",
            )
            material = Material.objects.create(
                name=f"Extra Feedstock {index}", publication_status="published"
            )
            showcase.showcase_materials.create(material=material, role="input")
            process = Process.objects.create(
                name=f"Extra Step {index}", publication_status="published"
            )
            showcase.showcase_processes.create(process=process, order=0)
        self.assertEqual(baseline, count_queries())
