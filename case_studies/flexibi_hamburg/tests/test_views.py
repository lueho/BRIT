from django.contrib.gis.geos import Point
from django.urls import reverse

from maps.models import (
    Catchment,
    GeoDataset,
    GeoPolygon,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    Region,
)
from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import HamburgRoadsideTrees


class HamburgRoadsideTreesMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["view_geodataset"]
    url_name = "HamburgRoadsideTrees"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        style = MapLayerStyle.objects.create(name="default")
        layer = MapLayerConfiguration.objects.create(
            name="default", layer_type="features", style=style
        )
        map_config = MapConfiguration.objects.create(name="default")
        map_config.layers.add(layer)
        cls.dataset = GeoDataset.objects.create(
            name="Hamburg Roadside Trees",
            description="Roadside trees in Hamburg",
            model_name="HamburgRoadsideTrees",
            region=Region.objects.create(name="Hamburg", country="Germany"),
            map_configuration=map_config,
        )
        cls.tree = HamburgRoadsideTrees.objects.create(geom=Point(0, 0, srid=4326))

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)


class HamburgRoadsideTreeCatchmentAutocompleteViewTests(ViewWithPermissionsTestCase):
    member_permissions = ["view_geodataset"]
    url_name = "hamburgroadsidetrees-catchment-autocomplete"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        # Create a GeoDataset and GeoPolygon for the borders
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 100, 100 100, 100 0, 0 0)))"
        )
        region = Region.objects.create(name="Hamburg", country="DE", borders=borders)

        cls.hamburg_catchment = Catchment.objects.create(
            name="Hamburg", region=region, publication_status="published"
        )
        cls.dataset = GeoDataset.objects.create(
            name="Hamburg Roadside Trees",
            description="Roadside trees in Hamburg",
            model_name="HamburgRoadsideTrees",
            region=region,
        )

        # Create a region within dataset borders
        inside = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((10 10, 10 90, 90 90, 90 10, 10 10)))"
        )
        inside_region = Region.objects.create(
            name="Inside", country="DE", borders=inside
        )
        cls.inside_catchment_1 = Catchment.objects.create(
            name="Inside 1", region=inside_region, publication_status="published"
        )

        # Create a second region within dataset borders
        inside_2 = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((20 20, 20 80, 80 80, 80 20, 20 20)))"
        )
        inside_region_2 = Region.objects.create(
            name="Inside 2", country="DE", borders=inside_2
        )
        cls.inside_catchment_2 = Catchment.objects.create(
            name="Inside 2", region=inside_region_2, publication_status="published"
        )

        # Create a region within dataset borders owned by outsider user
        inside_3 = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((30 30, 30 70, 70 70, 70 30, 30 30)))"
        )
        inside_region_3 = Region.objects.create(
            name="Inside 3", country="DE", borders=inside_3
        )
        cls.inside_outsider_catchment = Catchment.objects.create(
            name="Inside 3", region=inside_region_3, owner=cls.outsider
        )

        # Create a published region within dataset borders owned by outsider user
        inside_4 = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((40 40, 40 60, 60 60, 60 40, 40 40)))"
        )
        inside_region_4 = Region.objects.create(
            name="Inside 4", country="DE", borders=inside_4
        )
        cls.inside_outsider_catchment_published = Catchment.objects.create(
            name="Inside 4",
            region=inside_region_4,
            owner=cls.outsider,
            publication_status="published",
        )

        # Create a region completely outside dataset borders
        outside = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((200 200, 200 300, 300 300, 300 200, 200 200)))"
        )
        outside_region = Region.objects.create(
            name="Outside", country="DE", borders=outside
        )
        cls.outside_catchment = Catchment.objects.create(
            name="Outside", region=outside_region, publication_status="published"
        )

        # Create a region partially outside dataset borders
        partial = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((50 50, 50 150, 150 150, 150 50, 50 50)))"
        )
        partial_region = Region.objects.create(
            name="Partial", country="DE", borders=partial
        )
        cls.partial_catchment = Catchment.objects.create(
            name="Partial", region=partial_region, publication_status="published"
        )

        # Create a region outside dataset borders owned by outsider user
        outside_2 = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((400 400, 400 500, 500 500, 500 400, 400 400)))"
        )
        outside_region_2 = Region.objects.create(
            name="Outside 2", country="DE", borders=outside_2
        )
        cls.outside_outsider_catchment = Catchment.objects.create(
            name="Outside 2", region=outside_region_2, owner=cls.outsider
        )

    def test_only_inside_and_published_catchments_in_initial_queryset(self):
        response = self.client.get(reverse(self.url_name))
        expected_results = [
            {
                "id": self.hamburg_catchment.id,
                "name": "Hamburg",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_1.id,
                "name": "Inside 1",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_2.id,
                "name": "Inside 2",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_outsider_catchment_published.id,
                "name": "Inside 4",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
        ]
        actual_results = response.json()["results"]
        # Compare only the essential fields as TomSelect may include additional fields
        for expected, actual in zip(expected_results, actual_results):
            self.assertEqual(expected["id"], actual["id"])
            self.assertEqual(expected["name"], actual["name"])
            self.assertTrue(actual.get("can_view", False))

    def test_only_published_outsider_catchments_visible_to_other_users(self):
        response = self.client.get(reverse(self.url_name))
        expected_results = [
            {
                "id": self.hamburg_catchment.id,
                "name": "Hamburg",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_1.id,
                "name": "Inside 1",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_2.id,
                "name": "Inside 2",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_outsider_catchment_published.id,
                "name": "Inside 4",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
        ]
        actual_results = response.json()["results"]
        # Compare only the essential fields as TomSelect may include additional fields
        for expected, actual in zip(expected_results, actual_results):
            self.assertEqual(expected["id"], actual["id"])
            self.assertEqual(expected["name"], actual["name"])
            self.assertTrue(actual.get("can_view", False))

    def test_all_owned_and_published_catchments_visible_to_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name))
        expected_results = [
            {
                "id": self.hamburg_catchment.id,
                "name": "Hamburg",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_1.id,
                "name": "Inside 1",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_catchment_2.id,
                "name": "Inside 2",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_outsider_catchment.id,
                "name": "Inside 3",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
            {
                "id": self.inside_outsider_catchment_published.id,
                "name": "Inside 4",
                "can_view": True,
                "can_update": True,
                "can_delete": True,
            },
        ]
        actual_results = response.json()["results"]
        # Compare only the essential fields as TomSelect may include additional fields
        for expected, actual in zip(expected_results, actual_results):
            self.assertEqual(expected["id"], actual["id"])
            self.assertEqual(expected["name"], actual["name"])
            self.assertTrue(actual.get("can_view", False))
