"""Shared import machinery: the large-body JSON parser, the deferred
GeoJSON cache invalidation, and the shared-GeoPolygon update guard."""

import io
import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase, override_settings
from django.urls import reverse

from maps.models import LauRegion, NutsRegion, NutsVintage

GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[6.0, 47.0], [15.0, 47.0], [15.0, 55.0], [6.0, 55.0], [6.0, 47.0]]]
    ],
}
OTHER_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[9.0, 47.5], [13.0, 47.5], [13.0, 50.5], [9.0, 50.5], [9.0, 47.5]]]
    ],
}


def nuts_region(nuts_id, levl_code, geometry, **overrides):
    payload = {
        "nuts_id": nuts_id,
        "levl_code": levl_code,
        "cntr_code": nuts_id[:2],
        "name_latn": nuts_id,
        "geometry": geometry,
    }
    payload.update(overrides)
    return payload


class ImportBodySizeTestCase(TestCase):
    """The import parser must honour IMPORT_API_MAX_BODY_SIZE, not the global
    DATA_UPLOAD_MAX_MEMORY_SIZE."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user("bulk-loader")
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=(
                    "add_nutsregion",
                    "change_nutsregion",
                    "add_lauregion",
                    "change_lauregion",
                ),
            )
        )
        cls.user = user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._override = override_settings(
            DATA_UPLOAD_MAX_MEMORY_SIZE=1_000,
            IMPORT_API_MAX_BODY_SIZE=200_000,
        )
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        super().tearDownClass()

    def post(self, url, body):
        self.client.force_login(self.user)
        return self.client.post(url, body, content_type="application/json")

    def big_nuts_payload(self, count):
        """A payload padded past the test's tiny DATA_UPLOAD_MAX_MEMORY_SIZE
        by carrying many small regions."""
        return {
            "schema_version": "1.0",
            "dry_run": True,
            "vintage": {"year": 2010},
            "regions": [
                nuts_region(f"R{i:04d}", 0, GEOMETRY, cntr_code="DE")
                for i in range(count)
            ],
        }

    def big_lau_payload(self, count):
        return {
            "schema_version": "1.0",
            "dry_run": True,
            "vintage": {"year": 2018, "nuts_year": 2024},
            "regions": [
                {
                    "cntr_code": "DE",
                    "lau_id": f"{i:08d}",
                    "lau_name": f"LAU {i}",
                    "nuts_parent_id": None,
                    "geometry": GEOMETRY,
                }
                for i in range(count)
            ],
        }

    def test_a_50kb_body_is_accepted_by_the_nuts_import(self):
        body = json.dumps(self.big_nuts_payload(260))
        self.assertGreater(len(body), 50_000)
        response = self.post(reverse("nuts:import"), body)
        self.assertEqual(response.status_code, 200, response.content[:300])

    def test_a_50kb_body_is_accepted_by_the_lau_import(self):
        NutsVintage.objects.get_or_create(year=2024)
        body = json.dumps(self.big_lau_payload(260))
        self.assertGreater(len(body), 50_000)
        response = self.post(reverse("lau:import"), body)
        self.assertEqual(response.status_code, 200, response.content[:300])

    def test_a_body_over_the_import_limit_is_a_413(self):
        body = json.dumps(self.big_nuts_payload(2000))
        self.assertGreater(len(body), 200_000)
        response = self.post(reverse("nuts:import"), body)
        self.assertEqual(response.status_code, 413)

    def test_malformed_json_is_a_400(self):
        response = self.post(reverse("nuts:import"), "{not json")
        self.assertEqual(response.status_code, 400)

    def test_a_3d_geometry_is_imported_as_2d(self):
        """GeoJSON may carry [lon, lat, elev] positions; BRIT stores 2D."""
        polygon_3d = {
            "type": "Polygon",
            "coordinates": [
                [
                    [6.0, 47.0, 3.0],
                    [15.0, 47.0, 3.0],
                    [15.0, 55.0, 3.0],
                    [6.0, 55.0, 3.0],
                    [6.0, 47.0, 3.0],
                ]
            ],
        }
        response = self.post(
            reverse("nuts:import"),
            json.dumps(
                {
                    "schema_version": "1.0",
                    "vintage": {"year": 2010},
                    "regions": [nuts_region("DE3D", 0, polygon_3d)],
                }
            ),
        )
        self.assertEqual(response.status_code, 201, response.json())
        self.assertFalse(NutsRegion.objects.get(nuts_id="DE3D").borders.geom.hasz)

        NutsVintage.objects.get_or_create(year=2024)
        response = self.post(
            reverse("lau:import"),
            json.dumps(
                {
                    "schema_version": "1.0",
                    "vintage": {"year": 2018, "nuts_year": 2024},
                    "regions": [
                        {
                            "cntr_code": "DE",
                            "lau_id": "03003000",
                            "lau_name": "Elevated",
                            "nuts_parent_id": None,
                            "geometry": polygon_3d,
                        }
                    ],
                }
            ),
        )
        self.assertEqual(response.status_code, 201, response.json())
        self.assertFalse(LauRegion.objects.get(lau_id="03003000").borders.geom.hasz)

    def test_a_non_integer_content_length_does_not_500(self):
        """A junk CONTENT_LENGTH is treated as unknown; the read cap still
        enforces the limit."""
        from maps.import_common import ImportJSONParser

        request = Mock()
        request.META = {"CONTENT_LENGTH": "abc"}
        result = ImportJSONParser().parse(
            io.BytesIO(b'{"a": 1}'), parser_context={"request": request}
        )
        self.assertEqual(result, {"a": 1})


class DeferredGeojsonInvalidationTestCase(TestCase):
    """An N-row import must flush each distinct pattern once, not N times.

    TestCase keeps the import's atomic block as a savepoint, so
    ``captureOnCommitCallbacks`` can run the deferred flush the way a real
    commit would — and a rolled-back import never registers its callbacks.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user("nuts-loader")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=("add_nutsregion", "change_nutsregion"),
            )
        )
        self.url = reverse("nuts:import")

    def test_an_import_flushes_each_pattern_once(self):
        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        payload = {
            "schema_version": "1.0",
            "vintage": {"year": 2010},
            "regions": [
                nuts_region(f"D{i:02d}A", 0, GEOMETRY, cntr_code="DE")
                for i in range(20)
            ],
        }
        self.client.force_login(self.user)
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.url, payload, content_type="application/json"
                )
        self.assertEqual(response.status_code, 201, response.json())

        calls = geojson_cache.delete_pattern.call_args_list
        patterns = {str(c.args[0]) for c in calls}
        # 20 rows must not mean 20+ pattern deletes per signal.
        self.assertLessEqual(len(calls), 12)
        self.assertIn("nuts_geojson:*", patterns)

        # A geometry update saves the GeoPolygon a region already points at,
        # which is what invalidates the region-level caches.
        geojson_cache.reset_mock()
        payload["regions"] = [nuts_region("D00A", 0, OTHER_GEOMETRY, cntr_code="DE")]
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.url, payload, content_type="application/json"
                )
        self.assertEqual(response.json()["errors"], [])
        patterns = {str(c.args[0]) for c in geojson_cache.delete_pattern.call_args_list}
        self.assertIn("region_geojson:*", patterns)
        self.assertIn("catchment_geojson:*", patterns)
        self.assertIn("lau_geojson:*", patterns)

    def test_covered_patterns_are_flushed_only_by_the_broad_one(self):
        """`nuts_geojson:parent:3:*` and `nuts_geojson:id:3` add no extra SCAN
        once `nuts_geojson:*` is already pending."""
        from maps.signals import (
            clear_geojson_cache_pattern,
            deferred_geojson_invalidation,
        )

        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                with deferred_geojson_invalidation():
                    for pattern in (
                        "nuts_geojson:*",
                        "nuts_geojson:parent:3:*",
                        "nuts_geojson:id:3",
                        "lau_geojson:*",
                    ):
                        clear_geojson_cache_pattern(pattern)

        called = {str(c.args[0]) for c in geojson_cache.delete_pattern.call_args_list}
        self.assertEqual(
            called,
            {
                "nuts_geojson:*",
                "authz-v1:nuts_geojson:*",
                "lau_geojson:*",
                "authz-v1:lau_geojson:*",
            },
        )

    def test_a_dry_run_flushes_nothing(self):
        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        payload = {
            "schema_version": "1.0",
            "dry_run": True,
            "vintage": {"year": 2010},
            "regions": [nuts_region("DEA", 0, GEOMETRY)],
        }
        self.client.force_login(self.user)
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                self.client.post(self.url, payload, content_type="application/json")
        # A rolled-back import never registers its deferred flushes.
        self.assertEqual(callbacks, [])
        geojson_cache.delete_pattern.assert_not_called()


class SharedGeoPolygonGuardTestCase(TestCase):
    """Updating one region's geometry must not mutate a GeoPolygon another
    region still points at."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user("nuts-loader-2")
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=("add_nutsregion", "change_nutsregion"),
            )
        )
        cls.user = user
        cls.url = reverse("nuts:import")

    def post(self, regions):
        self.client.force_login(self.user)
        return self.client.post(
            self.url,
            {
                "schema_version": "1.0",
                "vintage": {"year": 2010},
                "regions": regions,
            },
            content_type="application/json",
        )

    def test_a_shared_polygon_gets_a_fresh_row(self):
        response = self.post([nuts_region("DE", 0, GEOMETRY)])
        self.assertEqual(response.status_code, 201, response.json())
        imported = NutsRegion.objects.get(nuts_id="DE", version__year=2010)
        other = NutsRegion.objects.create(
            name="Sharer",
            country="DE",
            nuts_id="DX",
            levl_code=0,
            cntr_code="DE",
            version=NutsVintage.current(),
            borders=imported.borders,
        )
        other_geom = other.geom.clone()

        response = self.post([nuts_region("DE", 0, OTHER_GEOMETRY)])
        self.assertEqual(response.json()["updated"], 1)

        imported.refresh_from_db()
        other.refresh_from_db()
        self.assertNotEqual(imported.borders_id, other.borders_id)
        self.assertTrue(other.geom.equals_exact(other_geom))
        self.assertTrue(
            imported.geom.equals_exact(
                GEOSGeometry(json.dumps(OTHER_GEOMETRY), srid=4326)
            )
        )


class GeometryChangeCacheFlushTestCase(TestCase):
    """A geometry change must flush region and catchment GeoJSON caches.

    The GeoPolygon post_save receiver only sees updates to a polygon a Region
    already points at; attaching a fresh GeoPolygon (new row or shared-polygon
    replacement) would otherwise leave stale tiles behind.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user("lau-loader")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=("add_lauregion", "change_lauregion"),
            )
        )
        self.vintage = NutsVintage.objects.create(year=2024)
        self.url = reverse("lau:import")

    def post(self, regions):
        self.client.force_login(self.user)
        return self.client.post(
            self.url,
            {
                "schema_version": "1.0",
                "vintage": {"year": 2018, "nuts_year": 2024},
                "regions": regions,
            },
            content_type="application/json",
        )

    def lau_row(self, geometry=GEOMETRY):
        return {
            "cntr_code": "DE",
            "lau_id": "01001000",
            "lau_name": "Flensburg",
            "nuts_parent_id": None,
            "geometry": geometry,
        }

    def test_creating_a_row_with_geometry_flushes_the_region_caches(self):
        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post([self.lau_row()])
        self.assertEqual(response.json()["created"], 1, response.json())
        patterns = {str(c.args[0]) for c in geojson_cache.delete_pattern.call_args_list}
        self.assertIn("region_geojson:*", patterns)
        self.assertIn("catchment_geojson:*", patterns)

    def test_a_name_only_change_flushes_the_region_caches(self):
        response = self.post([self.lau_row()])
        self.assertEqual(response.json()["created"], 1, response.json())

        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        row = self.lau_row()
        del row["geometry"]
        row["lau_name"] = "Flensburg renamed"
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post([row])
        self.assertEqual(response.json()["updated"], 1, response.json())
        patterns = {str(c.args[0]) for c in geojson_cache.delete_pattern.call_args_list}
        self.assertIn("region_geojson:*", patterns)

    def test_a_shared_polygon_replacement_flushes_the_region_caches(self):
        response = self.post([self.lau_row()])
        self.assertEqual(response.json()["created"], 1, response.json())
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        LauRegion.objects.create(
            name="Sharer",
            country="DE",
            cntr_code="DE",
            lau_id="02002000",
            year=2018,
            owner=self.user,
            borders=imported.borders,
        )

        geojson_cache = Mock()
        geojson_cache.delete_pattern = Mock(return_value=0)
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post([self.lau_row(OTHER_GEOMETRY)])
        self.assertEqual(response.json()["updated"], 1, response.json())
        patterns = {str(c.args[0]) for c in geojson_cache.delete_pattern.call_args_list}
        self.assertIn("region_geojson:*", patterns)
        self.assertIn("catchment_geojson:*", patterns)
