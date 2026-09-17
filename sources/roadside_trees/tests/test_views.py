import json
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse

from maps.models import (
    Catchment,
    GeoDataset,
    GeoDatasetRuntimeConfiguration,
    GeoPolygon,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    Region,
)
from maps.signals import get_geojson_cache
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

    def test_get_http_200_ok_via_maps_hamburg_prefix(self):
        response = self.client.get("/maps/hamburg/roadside_trees/map/")
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_via_sources_prefix(self):
        response = self.client.get("/sources/roadside_trees/map/")
        self.assertEqual(response.status_code, 200)

    def test_get_http_301_redirect_via_case_studies_hamburg_prefix(self):
        response = self.client.get(
            "/case_studies/hamburg/roadside_trees/map/",
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/sources/roadside_trees/map/")

    def test_case_studies_hamburg_redirect_preserves_query_string(self):
        response = self.client.get(
            "/case_studies/hamburg/roadside_trees/map/?stem_circumference_min=10",
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/sources/roadside_trees/map/?stem_circumference_min=10",
        )

    def test_dataset_map_route_uses_roadside_trees_plugin_runtime_compatibility(self):
        dataset = GeoDataset.objects.create(
            name="Hamburg Roadside Trees Runtime Dataset",
            owner=self.owner,
            publication_status="published",
            region=Region.objects.create(name="Hamburg Runtime", country="Germany"),
            map_configuration=self.dataset.map_configuration,
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            backend_type="django_model",
            runtime_model_name="HamburgRoadsideTrees",
        )

        response = self.client.get(reverse("geodataset-map", kwargs={"pk": dataset.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, dataset.name)
        self.assertContains(response, reverse("api-hamburg-roadside-trees-geojson"))

    def test_geojson_id_query_filters_to_single_tree(self):
        other_tree = HamburgRoadsideTrees.objects.create(geom=Point(1, 1, srid=4326))

        response = self.client.get(
            reverse("api-hamburg-roadside-trees-geojson"),
            {"id": other_tree.pk, "load_features": "true", "page": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Total-Count"], "1")
        data = json.loads(response.content)
        self.assertEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["id"], other_tree.pk)

    def test_geojson_head_preserves_bbox_metadata(self):
        outside = HamburgRoadsideTrees.objects.create(geom=Point(20, 20, srid=4326))
        url = reverse("api-hamburg-roadside-trees-geojson")
        params = {"bbox": "-1,-1,1,1", "stream": "true"}
        head = self.client.head(url, params, REMOTE_ADDR="10.9.9.9")
        get = self.client.get(url, params, REMOTE_ADDR="10.9.9.9")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(get.status_code, 200)
        self.assertEqual(b"".join(head.streaming_content), b"")
        self.assertFalse(hasattr(head, "data"))
        self.assertEqual(head["X-Total-Count"], "1")
        self.assertEqual(head["X-Data-Version"], get["X-Data-Version"])
        ids = {feature["id"] for feature in get.data["features"]}
        self.assertEqual(ids, {self.tree.pk})
        self.assertNotIn(outside.pk, ids)

    def test_geojson_version_changes_when_tree_data_changes(self):
        url = reverse("api-hamburg-roadside-trees-version")
        before = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        HamburgRoadsideTrees.objects.create(geom=Point(2, 2, srid=4326))
        after = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        self.assertNotEqual(before, after)

    def test_geojson_version_changes_when_tree_geom_updated(self):
        url = reverse("api-hamburg-roadside-trees-version")
        before = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        self.tree.geom = Point(5, 5, srid=4326)
        self.tree.save()
        after = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        self.assertNotEqual(before, after)

    def test_geojson_version_changes_on_reimport_preserving_ids(self):
        url = reverse("api-hamburg-roadside-trees-version")
        before = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        HamburgRoadsideTrees.objects.all().delete()
        HamburgRoadsideTrees.objects.create(
            id=self.tree.pk, geom=Point(9, 9, srid=4326)
        )
        after = self.client.get(url, REMOTE_ADDR="10.9.8.1").json()["version"]
        self.assertNotEqual(before, after)

    def test_geojson_get_returns_fresh_geometry_after_tree_change(self):
        # No cache clearing: the shared test cache is used by parallel
        # workers. Versioned keys make the assertions deterministic anyway —
        # a stale entry under the old version is simply never looked up.
        url = reverse("api-hamburg-roadside-trees-geojson")

        first = self.client.get(url, REMOTE_ADDR="10.9.8.5")
        self.assertEqual(first.status_code, 200)
        old_version = first["X-Data-Version"]
        self.assertEqual(
            list(json.loads(first.content)["features"][0]["geometry"]["coordinates"]),
            [0.0, 0.0],
        )

        self.tree.geom = Point(5, 5, srid=4326)
        self.tree.save()

        # The externally managed table changed, so the rotated dataset version
        # must orphan the stale payload instead of serving it.
        second = self.client.get(url, REMOTE_ADDR="10.9.8.5")
        self.assertEqual(second["X-Cache-Status"], "MISS")
        self.assertNotEqual(second["X-Data-Version"], old_version)
        self.assertEqual(
            list(json.loads(second.content)["features"][0]["geometry"]["coordinates"]),
            [5.0, 5.0],
        )

    @override_settings(
        GEOJSON_CACHE="geojson",
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "tree-warm-default",
            },
            "geojson": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "tree-warm-geojson",
            },
        },
    )
    def test_warmed_cache_head_never_reads_payload(self):
        # Isolated cache backend: the real geojson cache is shared across
        # parallel test workers, so clearing or relying on it would flake.
        from ..tasks import warm_roadside_tree_geojson_cache

        cache = get_geojson_cache()

        result = warm_roadside_tree_geojson_cache.run()
        self.assertEqual(result["status"], "success")

        version = self.client.get(
            reverse("api-hamburg-roadside-trees-version"), REMOTE_ADDR="10.9.8.3"
        ).json()["version"]
        cache_key = f"tree_geojson:all:dv:{version}"
        self.assertEqual(cache.get(f"{cache_key}:count"), 1)

        url = reverse("api-hamburg-roadside-trees-geojson")
        with patch.object(cache, "get", wraps=cache.get) as cache_get:
            head = self.client.head(url, REMOTE_ADDR="10.9.8.4")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head["X-Cache-Status"], "HIT")
        self.assertEqual(head["X-Total-Count"], "1")
        keys = [call.args[0] for call in cache_get.call_args_list]
        self.assertNotIn(cache_key, keys)


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
        for expected, actual in zip(expected_results, actual_results, strict=False):
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
        for expected, actual in zip(expected_results, actual_results, strict=False):
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
        for expected, actual in zip(expected_results, actual_results, strict=False):
            self.assertEqual(expected["id"], actual["id"])
            self.assertEqual(expected["name"], actual["name"])
            self.assertTrue(actual.get("can_view", False))
