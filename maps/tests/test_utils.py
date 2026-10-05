"""Tests for maps.utils helpers."""

import json
import zlib
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.test import SimpleTestCase, TestCase

from maps.models import Region
from maps.serializers import RegionGeoFeatureModelSerializer
from maps.utils import set_geojson_cache_payload
from utils.tests.testrunner import serial_test


class SetGeojsonCachePayloadTests(SimpleTestCase):
    def test_omitted_timeout_preserves_backend_default(self):
        cache = Mock()
        set_geojson_cache_payload(cache, "key", {"features": [1, 2]})
        # DEFAULT_TIMEOUT (not None) keeps the backend's configured expiry;
        # an explicit None would cache both entries permanently.
        self.assertEqual(
            [c.args[0] for c in cache.set.call_args_list],
            ["key", "key:count"],
        )
        for c in cache.set.call_args_list:
            self.assertIs(c.kwargs["timeout"], DEFAULT_TIMEOUT)

    def test_explicit_timeout_applies_to_payload_and_count(self):
        cache = Mock()
        set_geojson_cache_payload(cache, "key", {"features": []}, timeout=60)
        for c in cache.set.call_args_list:
            self.assertEqual(c.kwargs["timeout"], 60)

    def test_non_dict_payload_writes_no_count(self):
        cache = Mock()
        set_geojson_cache_payload(cache, "key", [1, 2])
        cache.set.assert_called_once_with("key", [1, 2], timeout=DEFAULT_TIMEOUT)


@serial_test
class RenderedGeojsonPayloadTests(TestCase):
    def setUp(self):
        self.region = Region(name='Quotes " and Unicode ä')
        self.region.geom = MultiPolygon(
            Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        )
        self.region.save()
        self.queryset = Region.objects.filter(pk=self.region.pk).select_related(
            "borders"
        )
        self.cache = caches[settings.GEOJSON_CACHE]
        self.cache.clear()
        self.addCleanup(self.cache.clear)

    def test_sql_geometry_matches_serializer_contract(self):
        from maps.utils import iter_geojson_features

        encoded = b"".join(
            iter_geojson_features(
                self.queryset, RegionGeoFeatureModelSerializer, "borders__geom"
            )
        )
        self.assertEqual(
            json.loads(encoded),
            RegionGeoFeatureModelSerializer(self.queryset, many=True).data,
        )

    def test_sql_rendering_holds_and_releases_a_memory_slot(self):
        from maps.utils import iter_geojson_features

        with patch("maps.utils.GEOJSON_RENDER_SLOTS", create=True) as slots:
            b"".join(
                iter_geojson_features(
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                )
            )
        slots.__enter__.assert_called_once()
        slots.__exit__.assert_called_once()

    def test_aborted_stream_releases_its_render_slot(self):
        from maps.utils import GEOJSON_RENDER_SLOTS, iter_geojson_features

        stream = iter_geojson_features(
            self.queryset, RegionGeoFeatureModelSerializer, "borders__geom"
        )
        next(stream)
        next(stream)
        stream.close()
        acquired = []
        try:
            for _ in range(2):
                acquired.append(GEOJSON_RENDER_SLOTS.acquire(blocking=False))
            self.assertTrue(all(acquired))
        finally:
            for held in acquired:
                if held:
                    GEOJSON_RENDER_SLOTS.release()

    def test_large_sql_result_releases_persistent_client_buffer(self):
        from maps.utils import iter_geojson_features

        connection = Mock(in_atomic_block=False)
        with (
            patch("maps.utils.connections", {"default": connection}, create=True),
            patch("maps.utils.GEOJSON_MAX_DB_RESULT_BYTES", 1, create=True),
        ):
            b"".join(
                iter_geojson_features(
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                )
            )
        connection.close.assert_called_once()

    def test_large_sql_result_does_not_close_an_atomic_transaction(self):
        from maps.utils import iter_geojson_features

        connection = Mock(in_atomic_block=True)
        with (
            patch("maps.utils.connections", {"default": connection}, create=True),
            patch("maps.utils.GEOJSON_MAX_DB_RESULT_BYTES", 1, create=True),
        ):
            b"".join(
                iter_geojson_features(
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                )
            )
        connection.close.assert_not_called()

    def test_cache_payload_is_incrementally_compressed(self):
        from maps.utils import cache_rendered_geojson

        cache_rendered_geojson(
            self.cache,
            "compressed",
            self.queryset,
            RegionGeoFeatureModelSerializer,
            "borders__geom",
        )
        data = json.loads(zlib.decompress(self.cache.get("compressed")))
        self.assertEqual(
            data, RegionGeoFeatureModelSerializer(self.queryset, many=True).data
        )

    def test_cached_decompression_output_chunks_are_bounded(self):
        from maps.utils import iter_rendered_geojson

        content = b"x" * 200_000
        chunks = list(iter_rendered_geojson(zlib.compress(content), chunk_size=32))
        self.assertEqual(b"".join(chunks), content)
        self.assertTrue(all(len(chunk) <= 32 for chunk in chunks))

    def test_rendered_cache_is_bounded_and_reused_without_serialization(self):
        from maps.utils import cache_rendered_geojson, rendered_geojson_cache_key

        key = rendered_geojson_cache_key("region_geojson:id:test", "dataset-version")
        self.assertTrue(
            cache_rendered_geojson(
                self.cache,
                key,
                self.queryset,
                RegionGeoFeatureModelSerializer,
                "borders__geom",
                timeout=60,
            )
        )
        self.assertIsInstance(self.cache.get(key), bytes)
        self.assertEqual(self.cache.get(f"{key}:count"), 1)
        with patch("maps.utils.iter_geojson_features", side_effect=AssertionError):
            self.assertFalse(
                cache_rendered_geojson(
                    self.cache,
                    key,
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                    timeout=60,
                )
            )

    def test_oversized_payload_does_not_enter_cache(self):
        from maps.utils import cache_rendered_geojson

        with patch("maps.utils.GEOJSON_MAX_RENDERED_CACHE_BYTES", 8):
            self.assertFalse(
                cache_rendered_geojson(
                    self.cache,
                    "large",
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                )
            )
        self.assertIsNone(self.cache.get("large"))
        self.assertIsNone(self.cache.get("large:count"))
        with (
            patch("maps.utils.GEOJSON_MAX_RENDERED_CACHE_BYTES", 8),
            patch("maps.utils.iter_geojson_features", side_effect=AssertionError),
        ):
            self.assertFalse(
                cache_rendered_geojson(
                    self.cache,
                    "large",
                    self.queryset,
                    RegionGeoFeatureModelSerializer,
                    "borders__geom",
                )
            )
