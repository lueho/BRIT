"""Tests for maps.utils helpers."""

from unittest.mock import Mock

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.test import SimpleTestCase

from maps.utils import set_geojson_cache_payload


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
