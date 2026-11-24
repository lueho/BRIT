from unittest.mock import Mock, call, patch

from django.db.models.signals import post_delete, post_save
from django.test import SimpleTestCase

from maps.models import (
    LauRegion,
    NutsRegion,
    RegionAttributeTextValue,
    RegionAttributeValue,
)


class SubclassRegionGeoJSONCacheInvalidationTests(SimpleTestCase):
    """Django only notifies the concrete sender: a LauRegion or NutsRegion
    save never reaches the ``sender=Region`` receiver, so the subclass
    receivers must drop the region namespace themselves."""

    def test_a_lau_region_save_clears_the_region_namespace(self):
        instance = LauRegion(id=5, owner_id=1)
        geojson_cache = Mock()
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            post_save.send(sender=LauRegion, instance=instance)
        geojson_cache.delete.assert_any_call("region_geojson:id:5")
        geojson_cache.delete_pattern.assert_any_call("region_geojson:*")

    def test_a_nuts_region_save_clears_the_region_namespace(self):
        instance = NutsRegion(id=7, owner_id=1)
        geojson_cache = Mock()
        with patch("maps.signals.get_geojson_cache", return_value=geojson_cache):
            post_save.send(sender=NutsRegion, instance=instance)
        geojson_cache.delete.assert_any_call("region_geojson:id:7")
        geojson_cache.delete_pattern.assert_any_call("region_geojson:*")


class RegionAttributeGeoJSONCacheInvalidationTests(SimpleTestCase):
    def test_numeric_attribute_save_and_delete_invalidate_region_geojson_cache(self):
        value = RegionAttributeValue(
            region_id=123,
            property_id=456,
            owner_id=1,
            value=12.5,
        )
        geojson_cache = Mock()

        with (
            patch("maps.signals.get_geojson_cache", return_value=geojson_cache),
            patch("maps.signals.clear_geojson_cache_pattern") as clear_pattern,
        ):
            post_save.send(sender=RegionAttributeValue, instance=value)
            post_delete.send(sender=RegionAttributeValue, instance=value)

        self.assertEqual(
            geojson_cache.delete.call_args_list,
            [
                call("region_geojson:id:123"),
                call("authz-v1:region_geojson:id:123"),
                call("region_geojson:id:123"),
                call("authz-v1:region_geojson:id:123"),
            ],
        )
        self.assertEqual(
            clear_pattern.call_args_list,
            [call("region_geojson:*"), call("region_geojson:*")],
        )

    def test_text_attribute_save_and_delete_invalidate_region_geojson_cache(self):
        value = RegionAttributeTextValue(
            region_id=123,
            categorical_attribute_id=789,
            owner_id=1,
            value="urban",
        )
        geojson_cache = Mock()

        with (
            patch("maps.signals.get_geojson_cache", return_value=geojson_cache),
            patch("maps.signals.clear_geojson_cache_pattern") as clear_pattern,
        ):
            post_save.send(sender=RegionAttributeTextValue, instance=value)
            post_delete.send(sender=RegionAttributeTextValue, instance=value)

        self.assertEqual(
            geojson_cache.delete.call_args_list,
            [
                call("region_geojson:id:123"),
                call("authz-v1:region_geojson:id:123"),
                call("region_geojson:id:123"),
                call("authz-v1:region_geojson:id:123"),
            ],
        )
        self.assertEqual(
            clear_pattern.call_args_list,
            [call("region_geojson:*"), call("region_geojson:*")],
        )
