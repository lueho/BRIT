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
from maps.models import Catchment, Region
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

    def test_private_region_name_hidden_from_readers_who_may_not_see_it(self):
        region = Region.objects.create(name="Secret Region", owner=self.owner)
        showcase = Showcase.objects.create(
            name="Private region showcase",
            region=region,
            publication_status="published",
        )
        data = ShowcaseFlatSerializer(showcase, context=_context()).data
        self.assertIsNone(data["region"])
        data = ShowcaseFlatSerializer(showcase, context=_context(self.owner)).data
        self.assertEqual("Secret Region", data["region"])

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
            "geom",
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

    def test_api_detail_includes_site_geometry(self):
        self.showcase.geom = Point(14, 55, srid=4326)
        self.showcase.save()
        response = self.client.get(
            reverse("api-showcase-detail", args=[self.showcase.pk])
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"type": "Point", "coordinates": [14.0, 55.0]}, response.json()["geom"]
        )

    def test_detail_geometry_is_null_without_a_site_not_a_region_centroid(self):
        self.showcase.region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 2, 2)))
        self.showcase.region.save()
        data = ShowcaseModelSerializer(self.showcase).data
        self.assertIsNone(data["geom"])

    def test_list_serializer_includes_site_geometry(self):
        self.showcase.geom = Point(14, 55, srid=4326)
        data = ShowcaseModelSerializer([self.showcase], many=True).data
        self.assertEqual(
            {"type": "Point", "coordinates": [14.0, 55.0]}, data[0]["geom"]
        )

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

    def test_properties_carry_the_showcase_code_for_map_labels(self):
        showcase = Showcase.objects.create(
            name="SC14 \u2013 Grass to protein",
            region=self.region,
            publication_status="published",
        )
        data = ShowcaseGeoFeatureModelSerializer(showcase).data
        self.assertEqual("SC14", data["properties"]["code"])

    def test_private_region_name_hidden_from_readers_who_may_not_see_it(self):
        owner = get_user_model().objects.create(username="geo_region_owner")
        region = Region.objects.create(name="Secret Region", owner=owner)
        showcase = Showcase.objects.create(
            name="SC20 \u2013 Private region",
            region=region,
            publication_status="published",
        )
        anonymous = ShowcaseGeoFeatureModelSerializer(showcase, context=_context()).data
        self.assertIsNone(anonymous["properties"]["region"])
        owned = ShowcaseGeoFeatureModelSerializer(
            showcase, context=_context(owner)
        ).data
        self.assertEqual("Secret Region", owned["properties"]["region"])

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

    def test_site_without_region_serializes_region_as_null(self):
        showcase = Showcase.objects.create(
            name="Regionless Site",
            geom=Point(14, 55, srid=4326),
            publication_status="published",
        )
        data = ShowcaseGeoFeatureModelSerializer(showcase).data
        self.assertIsNone(data["properties"]["region"])
        self.assertEqual(
            {"type": "Point", "coordinates": [14.0, 55.0]}, data["geometry"]
        )


class ShowcasePilotRegionGeoJSONTest(TestCase):
    """The showcase GeoJSON combines showcase site points with one
    pilot-region polygon per visible catchment (or the showcase's region for
    showcases without a catchment)."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create(username="pilot_region_owner")

        cls.catchment_region = Region.objects.create(
            name="TBN Region", publication_status="published"
        )
        cls.catchment_region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)))
        cls.catchment_region.save()
        cls.catchment = Catchment.objects.create(
            name="TBN Catchment",
            region=cls.catchment_region,
            publication_status="published",
        )
        cls.first = Showcase.objects.create(
            name="First Pilot",
            region=cls.catchment_region,
            catchment=cls.catchment,
            geom=Point(1, 2, srid=4326),
            publication_status="published",
        )
        cls.second = Showcase.objects.create(
            name="Second Pilot",
            catchment=cls.catchment,
            geom=Point(3, 4, srid=4326),
            publication_status="published",
        )

        cls.legacy_region = Region.objects.create(
            name="Legacy Region", publication_status="published"
        )
        cls.legacy_region.geom = MultiPolygon(Polygon.from_bbox((20, 20, 30, 30)))
        cls.legacy_region.save()
        cls.legacy = Showcase.objects.create(
            name="Legacy Showcase",
            region=cls.legacy_region,
            geom=Point(25, 25, srid=4326),
            publication_status="published",
        )

        cls.stray = Showcase.objects.create(
            name="Stray Showcase", publication_status="published"
        )

        cls.private_region = Region.objects.create(
            name="Private TBN Region", owner=cls.owner
        )
        cls.private_region.geom = MultiPolygon(Polygon.from_bbox((40, 40, 50, 50)))
        cls.private_region.save()
        cls.private_catchment = Catchment.objects.create(
            name="Private Catchment",
            region=cls.private_region,
            owner=cls.owner,
        )
        cls.private_link = Showcase.objects.create(
            name="Private Link",
            catchment=cls.private_catchment,
            geom=Point(45, 45, srid=4326),
            publication_status="published",
        )

        cls.hidden = Showcase.objects.create(
            name="Hidden Showcase",
            catchment=cls.catchment,
            geom=Point(5, 6, srid=4326),
            owner=cls.owner,
        )

    def _features(self, params=None, user=None):
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(
            reverse("api-showcase-geojson"), params or {"scope": "published"}
        )
        self.assertEqual(200, response.status_code)
        return response.json()["features"]

    @staticmethod
    def _pilots(features):
        return [
            f for f in features if f["properties"].get("feature_type") == "pilot_region"
        ]

    @staticmethod
    def _points(features):
        return [
            f for f in features if f["properties"].get("feature_type") == "showcase"
        ]

    def test_points_and_pilot_polygon_coexist(self):
        features = self._features()
        points = {f["id"]: f for f in self._points(features)}
        self.assertEqual(
            {"type": "Point", "coordinates": [1.0, 2.0]},
            points[self.first.pk]["geometry"],
        )
        pilots = {f["id"]: f for f in self._pilots(features)}
        catchment_feature = pilots[f"pilot-catchment-{self.catchment.pk}"]
        self.assertEqual("MultiPolygon", catchment_feature["geometry"]["type"])
        longitudes = [
            coord[0]
            for polygon in catchment_feature["geometry"]["coordinates"]
            for ring in polygon
            for coord in ring
        ]
        self.assertEqual(0.0, min(longitudes))
        self.assertEqual(10.0, max(longitudes))

    def test_shared_catchment_produces_one_polygon_listing_both_showcases(self):
        features = self._features()
        pilots = [
            f
            for f in self._pilots(features)
            if f["id"] == f"pilot-catchment-{self.catchment.pk}"
        ]
        self.assertEqual(1, len(pilots))
        self.assertEqual("TBN Catchment", pilots[0]["properties"]["name"])
        memberships = {
            entry["id"]: entry for entry in pilots[0]["properties"]["showcases"]
        }
        self.assertEqual(
            {"id": self.first.pk, "name": "First Pilot", "region": "TBN Region"},
            memberships[self.first.pk],
        )
        self.assertEqual(
            {"id": self.second.pk, "name": "Second Pilot", "region": None},
            memberships[self.second.pk],
        )

    def test_showcase_without_catchment_falls_back_to_region(self):
        features = self._features()
        pilots = {f["id"]: f for f in self._pilots(features)}
        fallback = pilots[f"pilot-region-{self.legacy_region.pk}"]
        self.assertEqual("Legacy Region", fallback["properties"]["name"])
        self.assertEqual("MultiPolygon", fallback["geometry"]["type"])
        self.assertEqual(
            [self.legacy.pk],
            [entry["id"] for entry in fallback["properties"]["showcases"]],
        )

    def test_showcase_without_region_or_catchment_does_not_crash(self):
        features = self._features()
        points = {f["id"]: f for f in self._points(features)}
        self.assertIn(self.stray.pk, points)
        self.assertIsNone(points[self.stray.pk]["geometry"])
        self.assertNotIn(
            self.stray.pk,
            [
                entry["id"]
                for pilot in self._pilots(features)
                for entry in pilot["properties"]["showcases"]
            ],
        )

    def test_private_catchment_geometry_hidden_from_anonymous(self):
        features = self._features()
        self.assertNotIn(
            f"pilot-catchment-{self.private_catchment.pk}",
            [f["id"] for f in self._pilots(features)],
        )
        self.assertNotIn(
            "Private Catchment",
            [f["properties"].get("name") for f in features],
        )
        self.assertIn(self.private_link.pk, [f["id"] for f in self._points(features)])

        features = self._features(user=self.owner)
        pilots = {f["id"]: f for f in self._pilots(features)}
        self.assertIn(f"pilot-catchment-{self.private_catchment.pk}", pilots)

    def test_private_catchment_does_not_fall_back_to_its_region_geometry(self):
        features = self._features()
        pilots = self._pilots(features)
        self.assertNotIn(
            f"pilot-region-{self.private_region.pk}", [f["id"] for f in pilots]
        )
        for pilot in pilots:
            longitudes = [
                coord[0]
                for polygon in pilot["geometry"]["coordinates"]
                for ring in polygon
                for coord in ring
            ]
            self.assertLess(max(longitudes), 40)

    def test_private_showcase_excluded_from_markers_and_pilot_membership(self):
        features = self._features()
        self.assertNotIn(self.hidden.pk, [f["id"] for f in self._points(features)])
        pilot = next(
            f
            for f in self._pilots(features)
            if f["id"] == f"pilot-catchment-{self.catchment.pk}"
        )
        self.assertNotIn(
            self.hidden.pk,
            [entry["id"] for entry in pilot["properties"]["showcases"]],
        )

        features = self._features({"scope": ""}, user=self.owner)
        self.assertIn(self.hidden.pk, [f["id"] for f in self._points(features)])
        pilot = next(
            f
            for f in self._pilots(features)
            if f["id"] == f"pilot-catchment-{self.catchment.pk}"
        )
        self.assertIn(
            self.hidden.pk,
            [entry["id"] for entry in pilot["properties"]["showcases"]],
        )

    def test_private_region_name_hidden_from_markers_and_pilot_members(self):
        showcase = Showcase.objects.create(
            name="Private Region Member",
            region=self.private_region,
            catchment=self.catchment,
            geom=Point(7, 7, srid=4326),
            publication_status="published",
        )
        features = self._features()
        point = next(f for f in self._points(features) if f["id"] == showcase.pk)
        self.assertIsNone(point["properties"]["region"])
        pilot = next(
            f
            for f in self._pilots(features)
            if f["id"] == f"pilot-catchment-{self.catchment.pk}"
        )
        member = next(
            entry
            for entry in pilot["properties"]["showcases"]
            if entry["id"] == showcase.pk
        )
        self.assertIsNone(member["region"])
        self.assertNotIn("Private TBN Region", str(features))

    def test_id_filter_reduces_pilot_membership(self):
        features = self._features({"id": self.first.pk})
        self.assertEqual([self.first.pk], [f["id"] for f in self._points(features)])
        pilots = self._pilots(features)
        self.assertEqual(1, len(pilots))
        self.assertEqual(
            [self.first.pk],
            [entry["id"] for entry in pilots[0]["properties"]["showcases"]],
        )

    def test_catchment_without_region_geometry_is_skipped(self):
        bald_region = Region.objects.create(name="Bald", publication_status="published")
        bald_catchment = Catchment.objects.create(
            name="Bald Catchment",
            region=bald_region,
            publication_status="published",
        )
        showcase = Showcase.objects.create(
            name="Bald Pilot",
            catchment=bald_catchment,
            geom=Point(7, 8, srid=4326),
            publication_status="published",
        )
        features = self._features({"id": showcase.pk})
        self.assertEqual([], self._pilots(features))
        self.assertEqual([showcase.pk], [f["id"] for f in self._points(features)])


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
        self.assertEqual(
            {"maps_catchment"},
            self._queried_connection_tables("api-showcase-geojson"),
        )

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
