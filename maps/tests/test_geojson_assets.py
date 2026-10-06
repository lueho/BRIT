import json
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from maps import geojson_assets
from maps.geojson_assets import (
    get_static_region_geojson_asset_name,
    get_static_region_geojson_url,
    get_static_region_geojson_version,
    is_static_region_geojson_eligible,
)
from maps.mixins import CachedGeoJSONMixin
from maps.models import GeoPolygon, Region
from maps.tasks import warm_static_region_geojson_assets
from maps.utils import get_region_cache_key
from maps.utils import iter_geojson_features as real_iter_geojson_features
from maps.views import MapMixin
from utils.tests.testrunner import serial_test

STATIC_NAME = "Europe (NUTS)"


class RenamingStorage(FileSystemStorage):
    def save(self, name, content, max_length=None):
        return super().save(name + ".renamed", content)


def _geom():
    return MultiPolygon(Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))))


def create_region(name="Region", publication_status="published", with_geom=True):
    region = Region(name=name, publication_status=publication_status, country="ZZ")
    if with_geom:
        region.geom = _geom()
    region.save()
    return region


@serial_test
@override_settings(GEOJSON_STATIC_REGION_NAMES=(STATIC_NAME,))
class StaticRegionGeoJSONAssetTests(TestCase):
    def setUp(self):
        self.geojson_cache = caches[settings.GEOJSON_CACHE]
        self.geojson_cache.clear()
        self.addCleanup(self.geojson_cache.clear)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.storage = FileSystemStorage(location=self.tmpdir.name)
        patcher = patch("maps.geojson_assets.default_storage", self.storage)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.region = create_region(name=STATIC_NAME)
        self.region = Region.objects.get(pk=self.region.pk)
        self.version = get_static_region_geojson_version(self.region)
        self.asset_url = reverse(
            "region-geojson-asset",
            kwargs={"pk": self.region.pk, "version": self.version},
        )
        self.api_url = reverse("api-region-geojson")
        self.api_version_url = reverse("api-region-version")

    def _asset_payload(self, response):
        return json.loads(b"".join(response.streaming_content))

    def test_eligibility_and_url(self):
        self.assertTrue(is_static_region_geojson_eligible(self.region))
        self.assertEqual(get_static_region_geojson_url(self.region), self.asset_url)
        private_region = create_region(name=STATIC_NAME, publication_status="private")
        self.assertIsNone(get_static_region_geojson_url(private_region))
        unnamed = create_region(name="Other", publication_status="published")
        self.assertIsNone(get_static_region_geojson_url(unnamed))
        no_borders = create_region(name=STATIC_NAME, with_geom=False)
        self.assertIsNone(get_static_region_geojson_url(no_borders))

    def test_api_geojson_redirects_to_asset_with_same_payload(self):
        response = self.client.get(self.api_url, {"id": self.region.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Data-Version"], self.version)
        self.assertEqual(response["X-Total-Count"], "1")
        self.assertTrue(response["Location"].endswith(self.asset_url))

        followed = self.client.get(self.api_url, {"id": self.region.pk}, follow=True)
        self.assertEqual(followed.status_code, 200)
        self.assertEqual(followed["Content-Type"], "application/geo+json")
        self.assertEqual(followed["ETag"], f'"{self.version}"')
        self.assertEqual(followed["X-Data-Version"], self.version)
        self.assertEqual(followed["X-Total-Count"], "1")
        self.assertEqual(followed["X-Cache-Status"], "ASSET")
        self.assertEqual(
            followed["Cache-Control"], "public, max-age=31536000, immutable"
        )
        data = self._asset_payload(followed)
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        feature = data["features"][0]
        self.assertEqual(feature["properties"]["name"], STATIC_NAME)
        self.assertEqual(feature["properties"]["country"], self.region.country)
        self.assertEqual(feature["geometry"]["type"], "MultiPolygon")

    def test_redirect_path_does_not_load_geometry(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.api_url, {"id": self.region.pk})
        self.assertEqual(response.status_code, 302)
        geom_column = f'"{GeoPolygon._meta.db_table}"."geom"::bytea'
        self.assertFalse(any(geom_column in q["sql"] for q in queries))
        self.assertFalse(any("ST_AsGeoJSON" in q["sql"] for q in queries))

    def test_first_asset_render_uses_postgis_not_geos(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.asset_url)
            self.assertEqual(response.status_code, 200)
            self._asset_payload(response)
        geom_column = f'"{GeoPolygon._meta.db_table}"."geom"::bytea'
        self.assertFalse(any(geom_column in q["sql"] for q in queries))
        self.assertTrue(any("ST_AsGeoJSON" in q["sql"] for q in queries))
        self.assertTrue(self.storage.exists(self._asset_name()))

    def _asset_name(self):
        return get_static_region_geojson_asset_name(self.region.pk, self.version)

    def test_asset_is_not_regenerated_after_first_write(self):
        with patch(
            "maps.utils.iter_geojson_features",
            wraps=real_iter_geojson_features,
        ) as render:
            first = self.client.get(self.asset_url)
            self.assertEqual(first.status_code, 200)
            self._asset_payload(first)
            self.assertEqual(render.call_count, 1)

            second = self.client.get(self.asset_url)
            self.assertEqual(second.status_code, 200)
            self.geojson_cache.clear()
            third = self.client.get(self.asset_url)
            self.assertEqual(third.status_code, 200)
            Region.objects.filter(pk=self.region.pk).update(name=self.region.name)
            create_region(name="Unrelated")
            fourth = self.client.get(self.asset_url)
            self.assertEqual(fourth.status_code, 200)
            warm_static_region_geojson_assets.apply()
            fifth = self.client.get(self.asset_url)
            self.assertEqual(fifth.status_code, 200)
            self.assertEqual(render.call_count, 1)
        self.assertTrue(self.storage.exists(self._asset_name()))

    def test_country_change_and_same_second_microseconds_rotate_token(self):
        Region.objects.filter(pk=self.region.pk).update(country="AA")
        self.assertNotEqual(
            get_static_region_geojson_version(Region.objects.get(pk=self.region.pk)),
            self.version,
        )

        base = self.region.lastmodified_at.replace(microsecond=0)
        first = base.replace(microsecond=111111)
        second = base.replace(microsecond=222222)
        Region.objects.filter(pk=self.region.pk).update(lastmodified_at=first)
        token_one = get_static_region_geojson_version(
            Region.objects.get(pk=self.region.pk)
        )
        Region.objects.filter(pk=self.region.pk).update(lastmodified_at=second)
        token_two = get_static_region_geojson_version(
            Region.objects.get(pk=self.region.pk)
        )
        self.assertNotEqual(token_one, token_two)

    def test_metadata_change_rotates_asset_and_stale_url_404s(self):
        response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self._asset_payload(response)

        Region.objects.filter(pk=self.region.pk).update(description="updated")
        refreshed = Region.objects.get(pk=self.region.pk)
        new_version = get_static_region_geojson_version(refreshed)
        self.assertNotEqual(new_version, self.version)

        stale = self.client.get(self.asset_url)
        self.assertEqual(stale.status_code, 404)

        new_url = reverse(
            "region-geojson-asset",
            kwargs={"pk": self.region.pk, "version": new_version},
        )
        response = self.client.get(new_url)
        self.assertEqual(response.status_code, 200)
        data = self._asset_payload(response)
        self.assertEqual(data["features"][0]["properties"]["description"], "updated")

    def test_geometry_change_rotates_version(self):
        self.region.geom = MultiPolygon(
            Polygon(((0, 0), (2, 0), (2, 2), (0, 2), (0, 0)))
        )
        self.region.save()
        refreshed = Region.objects.get(pk=self.region.pk)
        self.assertNotEqual(get_static_region_geojson_version(refreshed), self.version)
        self.assertEqual(self.client.get(self.asset_url).status_code, 404)

    def test_schema_version_bump_rotates_token(self):
        with patch("maps.geojson_assets.REGION_GEOJSON_ASSET_SCHEMA_VERSION", 2):
            bumped = get_static_region_geojson_version(self.region)
        self.assertNotEqual(bumped, self.version)
        self.assertEqual(len(bumped), 32)

    def test_ineligible_regions_cannot_be_fetched_or_redirected(self):
        private_region = create_region(name=STATIC_NAME, publication_status="private")
        version = get_static_region_geojson_version(private_region)
        url = reverse(
            "region-geojson-asset",
            kwargs={"pk": private_region.pk, "version": version},
        )
        self.assertEqual(self.client.get(url).status_code, 404)

        response = self.client.get(self.api_url, {"id": private_region.pk})
        self.assertNotEqual(response.status_code, 302)

        unnamed = create_region(name="Other")
        response = self.client.get(self.api_url, {"id": unnamed.pk})
        self.assertNotEqual(response.status_code, 302)

        no_borders = create_region(name=STATIC_NAME, with_geom=False)
        response = self.client.get(self.api_url, {"id": no_borders.pk})
        self.assertNotEqual(response.status_code, 302)

        missing = reverse(
            "region-geojson-asset",
            kwargs={"pk": 999999, "version": "0" * 32},
        )
        self.assertEqual(self.client.get(missing).status_code, 404)

    def test_direct_asset_404_for_unnominated_and_borderless_region(self):
        unnominated = create_region(name="Other")
        url = reverse(
            "region-geojson-asset",
            kwargs={
                "pk": unnominated.pk,
                "version": get_static_region_geojson_version(unnominated),
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)

        no_borders = create_region(name=STATIC_NAME, with_geom=False)
        url = reverse(
            "region-geojson-asset",
            kwargs={
                "pk": no_borders.pk,
                "version": get_static_region_geojson_version(no_borders),
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_withdrawal_invalidates_existing_asset_url(self):
        response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self._asset_payload(response)
        Region.objects.filter(pk=self.region.pk).update(publication_status="private")
        self.assertEqual(self.client.get(self.asset_url).status_code, 404)
        response = self.client.get(self.api_url, {"id": self.region.pk})
        self.assertNotEqual(response.status_code, 302)

    def test_non_simple_requests_fall_back_to_existing_behaviour(self):
        cases = [
            {"id": [self.region.pk, 123]},
            {"id": self.region.pk, "name": STATIC_NAME},
            {"id": self.region.pk, "stream": "true"},
            {"id": "not-an-int"},
        ]
        for params in cases:
            response = self.client.get(self.api_url, params)
            self.assertNotEqual(
                response.status_code, 302, f"unexpected redirect for {params}"
            )
            self.assertNotEqual(response.status_code, 404)

    def test_bbox_requests_are_delegated_to_mixin(self):
        from django.http import HttpResponse

        sentinel = HttpResponse(status=204)
        with patch.object(
            CachedGeoJSONMixin, "geojson", autospec=True, return_value=sentinel
        ) as mixin_geojson:
            response = self.client.get(
                self.api_url, {"id": self.region.pk, "bbox": "0,0,2,2"}
            )
        mixin_geojson.assert_called_once()
        self.assertEqual(response.status_code, 204)

    def test_version_endpoint_returns_asset_token_for_eligible_region(self):
        response = self.client.get(self.api_version_url, {"id": self.region.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], self.version)
        self.assertEqual(response["X-Data-Version"], self.version)

        other = create_region(name="Other")
        response = self.client.get(self.api_version_url, {"id": other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["version"], self.version)

    def test_head_and_if_none_match_do_not_render(self):
        with patch(
            "maps.utils.iter_geojson_features",
            wraps=real_iter_geojson_features,
        ) as render:
            head = self.client.head(self.asset_url)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(b"".join(head.streaming_content), b"")
            self.assertEqual(head["X-Data-Version"], self.version)
            self.assertEqual(head["X-Total-Count"], "1")
            self.assertEqual(head["ETag"], f'"{self.version}"')
            self.assertEqual(render.call_count, 0)

            self.client.get(self.asset_url)
            self.assertEqual(render.call_count, 1)

            head = self.client.head(self.asset_url)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(b"".join(head.streaming_content), b"")
            self.assertEqual(head["X-Cache-Status"], "ASSET")
            self.assertEqual(
                head["Cache-Control"], "public, max-age=31536000, immutable"
            )

            conditional = self.client.get(
                self.asset_url, HTTP_IF_NONE_MATCH=f'"{self.version}"'
            )
            self.assertEqual(conditional.status_code, 304)
            weak = self.client.get(
                self.asset_url, HTTP_IF_NONE_MATCH=f'W/"{self.version}"'
            )
            self.assertEqual(weak.status_code, 304)
            multi = self.client.get(
                self.asset_url,
                HTTP_IF_NONE_MATCH=f'"deadbeef", "{self.version}"',
            )
            self.assertEqual(multi.status_code, 304)
            self.assertEqual(render.call_count, 1)

    def test_storage_failure_falls_back_to_fresh_no_store_stream(self):
        with patch.object(self.storage, "exists", side_effect=OSError("storage down")):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = self._asset_payload(response)
        self.assertEqual(len(data["features"]), 1)

    def test_busy_generation_lock_falls_back_to_fresh_no_store_stream(self):
        name = self._asset_name()
        self.geojson_cache.set(f"region_geojson_asset:lock:{name}", True)
        response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["X-Cache-Status"], "STREAM")
        data = self._asset_payload(response)
        self.assertEqual(len(data["features"]), 1)
        self.assertFalse(self.storage.exists(name))

    def test_compressed_size_cap_falls_back_to_no_store_stream(self):
        with patch("maps.utils.GEOJSON_MAX_RENDERED_CACHE_BYTES", 4):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = self._asset_payload(response)
        self.assertEqual(len(data["features"]), 1)
        self.assertFalse(self.storage.exists(self._asset_name()))

    def test_oversized_stored_asset_is_rejected(self):
        name = self._asset_name()
        self.storage.save(name, ContentFile(b"x" * (8 * 1024 * 1024 + 1)))
        response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = self._asset_payload(response)
        self.assertEqual(len(data["features"]), 1)

    def test_map_config_swaps_standard_region_url_for_eligible_region(self):
        mixin = MapMixin()
        config = {
            "regionId": self.region.pk,
            "regionLayerGeometriesUrl": self.api_url,
            "loadRegion": True,
        }
        processed = mixin.post_process_map_config(dict(config))
        self.assertEqual(processed["regionLayerGeometriesUrl"], self.asset_url)
        self.assertEqual(processed["regionLayerDynamicGeometriesUrl"], self.api_url)
        self.assertTrue(processed["loadRegion"])

    def test_map_config_url_recognition_rejects_foreign_and_filtered_urls(self):
        mixin = MapMixin()
        for url in (
            f"{self.api_url}?id={self.region.pk}",
            "https://other.example.com/maps/api/region/geojson/",
        ):
            config = {
                "regionId": self.region.pk,
                "regionLayerGeometriesUrl": url,
                "loadRegion": True,
            }
            processed = mixin.post_process_map_config(dict(config))
            self.assertEqual(processed["regionLayerGeometriesUrl"], url)
            self.assertNotIn("regionLayerDynamicGeometriesUrl", processed)

    def test_map_config_absolute_same_origin_url_is_swapped(self):
        from django.test import RequestFactory

        mixin = MapMixin()
        mixin.request = RequestFactory().get("/")
        same_origin = f"http://testserver{self.api_url}"
        config = {
            "regionId": self.region.pk,
            "regionLayerGeometriesUrl": same_origin,
            "loadRegion": True,
        }
        processed = mixin.post_process_map_config(dict(config))
        self.assertEqual(processed["regionLayerGeometriesUrl"], self.asset_url)
        self.assertEqual(processed["regionLayerDynamicGeometriesUrl"], same_origin)

        config = {
            "regionId": self.region.pk,
            "regionLayerGeometriesUrl": "http://other.example.com" + self.api_url,
            "loadRegion": True,
        }
        processed = mixin.post_process_map_config(dict(config))
        self.assertNotEqual(processed["regionLayerGeometriesUrl"], self.asset_url)

    def test_map_config_leaves_other_urls_and_regions_alone(self):
        mixin = MapMixin()
        custom = {
            "regionId": self.region.pk,
            "regionLayerGeometriesUrl": "https://example.com/custom.geojson",
            "loadRegion": True,
        }
        processed = mixin.post_process_map_config(dict(custom))
        self.assertEqual(
            processed["regionLayerGeometriesUrl"], custom["regionLayerGeometriesUrl"]
        )

        other = create_region(name="Other")
        config = {
            "regionId": other.pk,
            "regionLayerGeometriesUrl": self.api_url,
            "loadRegion": True,
        }
        processed = mixin.post_process_map_config(dict(config))
        self.assertEqual(processed["regionLayerGeometriesUrl"], self.api_url)

    def test_storage_save_returning_different_name_is_served(self):
        storage = RenamingStorage(location=self.tmpdir.name)
        with patch("maps.geojson_assets.default_storage", storage):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Cache-Status"], "ASSET")
        data = self._asset_payload(response)
        self.assertEqual(len(data["features"]), 1)
        self.assertTrue(storage.exists(self._asset_name() + ".renamed"))

    def test_metadata_edit_during_render_aborts_save_and_stale_url_404s(self):
        real_render = geojson_assets.render_geojson_payload

        def render_then_edit(*args, **kwargs):
            payload = real_render(*args, **kwargs)
            Region.objects.filter(pk=self.region.pk).update(description="mid-render")
            return payload

        with patch(
            "maps.geojson_assets.render_geojson_payload",
            side_effect=render_then_edit,
        ):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.storage.exists(self._asset_name()))

        refreshed = Region.objects.get(pk=self.region.pk)
        new_url = reverse(
            "region-geojson-asset",
            kwargs={
                "pk": self.region.pk,
                "version": get_static_region_geojson_version(refreshed),
            },
        )
        response = self.client.get(new_url)
        self.assertEqual(response.status_code, 200)
        data = self._asset_payload(response)
        self.assertEqual(data["features"][0]["properties"]["description"], "mid-render")

    def test_withdrawal_during_render_aborts_save_and_url_404s(self):
        real_render = geojson_assets.render_geojson_payload

        def render_then_withdraw(*args, **kwargs):
            payload = real_render(*args, **kwargs)
            Region.objects.filter(pk=self.region.pk).update(
                publication_status="private"
            )
            return payload

        with patch(
            "maps.geojson_assets.render_geojson_payload",
            side_effect=render_then_withdraw,
        ):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.storage.exists(self._asset_name()))

    def test_replaced_lock_owner_is_not_deleted_on_release(self):
        if not hasattr(self.geojson_cache, "lock"):
            self.skipTest("lock ownership test requires a lock-capable cache")
        lock_key = f"region_geojson_asset:lock:{self._asset_name()}"
        real_render = geojson_assets.render_geojson_payload

        def render_then_replace_owner(*args, **kwargs):
            payload = real_render(*args, **kwargs)
            self.geojson_cache.set(lock_key, "other-owner")
            return payload

        with (
            patch(
                "maps.geojson_assets.render_geojson_payload",
                side_effect=render_then_replace_owner,
            ),
            patch.object(
                self.geojson_cache, "delete", wraps=self.geojson_cache.delete
            ) as delete_spy,
        ):
            response = self.client.get(self.asset_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.geojson_cache.get(lock_key), "other-owner")
        self.assertNotIn(lock_key, [call.args[0] for call in delete_spy.call_args_list])


@serial_test
@override_settings(GEOJSON_STATIC_REGION_NAMES=(STATIC_NAME,))
class StaticRegionGeoJSONWarmupTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        self.geojson_cache = caches[settings.GEOJSON_CACHE]
        self.geojson_cache.clear()
        self.addCleanup(self.geojson_cache.clear)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.storage = FileSystemStorage(location=self.tmpdir.name)
        patcher = patch("maps.geojson_assets.default_storage", self.storage)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_region_warmup_excludes_static_regions(self):
        from maps.cache_warmup import warm_region_geojson_cache

        static_region = create_region(name=STATIC_NAME)
        plain_region = create_region(name="Plain region")
        warm_region_geojson_cache(limit=10)
        self.assertIsNone(
            self.geojson_cache.get(get_region_cache_key(region_id=static_region.pk))
        )
        self.assertIsNotNone(
            self.geojson_cache.get(get_region_cache_key(region_id=plain_region.pk))
        )

    def test_static_warmup_builds_missing_asset_only_once(self):
        static_region = create_region(name=STATIC_NAME)
        create_region(name="Other")
        with patch(
            "maps.geojson_assets.render_geojson_payload",
            wraps=geojson_assets.render_geojson_payload,
        ) as render:
            result = warm_static_region_geojson_assets.apply()
            self.assertTrue(result.successful())
            self.assertEqual(render.call_count, 1)
            version = get_static_region_geojson_version(
                Region.objects.get(pk=static_region.pk)
            )
            self.assertTrue(
                self.storage.exists(
                    get_static_region_geojson_asset_name(static_region.pk, version)
                )
            )
            result = warm_static_region_geojson_assets.apply()
            self.assertTrue(result.successful())
            self.assertEqual(render.call_count, 1)

    @override_settings(GEOJSON_STATIC_REGION_NAMES=("Alpha static", "Beta static"))
    def test_static_warmup_survives_connection_close_between_regions(self):
        first = create_region(name="Alpha static")
        second = create_region(name="Beta static")
        real_render = geojson_assets.render_geojson_payload
        calls = []

        def render_and_close(*args, **kwargs):
            calls.append(1)
            payload = real_render(*args, **kwargs)
            connection.close()
            return payload

        with patch(
            "maps.geojson_assets.render_geojson_payload",
            side_effect=render_and_close,
        ):
            result = warm_static_region_geojson_assets.apply()
        self.assertTrue(result.successful())
        self.assertEqual(len(calls), 2)
        for region in (first, second):
            refreshed = Region.objects.get(pk=region.pk)
            self.assertTrue(
                self.storage.exists(
                    get_static_region_geojson_asset_name(
                        region.pk,
                        get_static_region_geojson_version(refreshed),
                    )
                )
            )
