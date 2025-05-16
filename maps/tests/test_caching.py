import io

from django.conf import settings
from django.core.cache import caches
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from ..models import NutsRegion, Region
from ..utils import get_region_cache_key


class GeoJSONCachingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.region1 = Region.objects.create(name="TestRegion1")
        cls.region2 = Region.objects.create(name="TestRegion2")
        cls.regions_geojson_url = reverse("api-region-geojson")

    def setUp(self):
        self.geojson_cache = caches[settings.GEOJSON_CACHE]
        self.geojson_cache.clear()

    def tearDown(self):
        self.geojson_cache.clear()

    def test_geojson_cache_miss_and_hit(self):
        """Verify first request is MISS, second is HIT with correct headers."""
        url = self.regions_geojson_url + "?name=TestRegion1"  # Example filter

        # 1. First request (MISS)
        response_miss = self.client.get(url)
        self.assertEqual(response_miss.status_code, 200)
        self.assertEqual(response_miss["X-Cache-Status"], "MISS")
        self.assertTrue("X-Cache-Time" in response_miss)
        self.assertContains(response_miss, "TestRegion1")

        # Verify cache key was set
        expected_key = get_region_cache_key(filters={"name": "TestRegion1"})
        self.assertIsNotNone(self.geojson_cache.get(expected_key))

        # 2. Second request (HIT)
        # Sleep slightly MORE than typical request time to ensure time diff is measurable
        # time.sleep(0.01) # Usually not needed unless testing time precisely
        response_hit = self.client.get(url)
        self.assertEqual(response_hit.status_code, 200)
        self.assertEqual(response_hit["X-Cache-Status"], "HIT")
        self.assertTrue("X-Cache-Time" in response_hit)
        self.assertEqual(response_miss.content, response_hit.content)

    def test_cache_invalidation_on_save(self):
        """Verify cache is invalidated when a relevant model instance is saved."""
        url = f"{reverse('api-region-geojson')}?id={self.region1.pk}"
        list_url = self.regions_geojson_url
        list_key = get_region_cache_key(filters=None)
        detail_key = get_region_cache_key(region_id=self.region1.pk)

        # 1. Populate cache for detail and list
        self.client.get(url)
        self.client.get(list_url)
        self.assertIsNotNone(
            self.geojson_cache.get(detail_key), "Detail key not cached"
        )
        self.assertIsNotNone(self.geojson_cache.get(list_key), "List key not cached")

        # 2. Modify and save the instance (triggers post_save signal)
        self.region1.name = "UpdatedRegion1"
        self.region1.save()

        # 3. Verify cache keys are gone (due to specific DEL and pattern DEL)
        self.assertIsNone(
            self.geojson_cache.get(detail_key), "Specific detail key not invalidated"
        )
        # The pattern delete ('region_geojson:*') should have cleared the list key too
        self.assertIsNone(
            self.geojson_cache.get(list_key), "List key not invalidated by pattern"
        )

        # 4. Verify next request is a MISS
        response_after_save = self.client.get(url)
        self.assertEqual(response_after_save["X-Cache-Status"], "MISS")
        response_list_after_save = self.client.get(list_url)
        self.assertEqual(response_list_after_save["X-Cache-Status"], "MISS")

    def test_cache_invalidation_on_delete(self):
        """Verify cache is invalidated when a relevant model instance is deleted."""
        list_url = self.regions_geojson_url
        list_key = get_region_cache_key(filters=None)
        detail_key = get_region_cache_key(region_id=self.region1.pk)

        self.client.get(list_url)
        self.assertIsNotNone(self.geojson_cache.get(list_key))

        region_id_to_delete = self.region1.id
        self.region1.delete()  # Triggers post_delete signal

        self.assertIsNone(
            self.geojson_cache.get(detail_key), "Detail key not invalidated on delete"
        )
        self.assertIsNone(
            self.geojson_cache.get(list_key),
            "List key not invalidated by pattern on delete",
        )

        # Verify list view MISS and doesn't contain the deleted region
        response_after_delete = self.client.get(list_url)
        self.assertEqual(response_after_delete["X-Cache-Status"], "MISS")
        self.assertNotContains(response_after_delete, f"Region{region_id_to_delete}")

    def test_warmup_command(self):
        """Test the warmup_geojson_cache management command."""
        NutsRegion.objects.create(levl_code=0)
        NutsRegion.objects.create(levl_code=1)

        # Capture command output
        out = io.StringIO()
        call_command("warmup_geojson_cache", "--nuts-levels=0", stdout=out)

        self.assertIn("Warming up GeoJSON cache...", out.getvalue())
        self.assertIn("Caching NUTS level 0 regions...", out.getvalue())
        self.assertIn("Cache warmup complete!", out.getvalue())

        # Verify cache keys were set
        # Note: Adjust key format based on your final get_nuts_region_cache_key logic
        expected_key_level_0_list = "nuts_geojson:level:0"
        self.assertIsNotNone(self.geojson_cache.get(expected_key_level_0_list))
        # Add checks for specific NUTS ID keys if warmed up

    def test_monitor_command(self):
        """Test the monitor_cache command executes and shows info."""
        self.client.get(self.regions_geojson_url)

        out = io.StringIO()
        # Use try-except as command might fail if Redis isn't configured correctly for test env
        try:
            call_command("monitor_cache", stdout=out)
        except Exception as e:
            self.fail(f"monitor_cache command failed: {e}")

        output = out.getvalue()
        self.assertIn("Monitoring GeoJSON cache usage", output)
        self.assertIn("Redis version:", output)
        self.assertIn(
            "GeoJSON keys found (via SCAN):", output
        )  # Check for SCAN usage indicator
        # Check if the specific cached key appears in the output (might be fragile)
        self.assertIn("region_geojson:", output)

    def test_clear_cache_command(self):
        """Test the clear_geojson_cache management command."""
        # 1. Populate cache
        key_to_clear = get_region_cache_key(filters={"name": "Test Region 1"})
        self.client.get(self.regions_geojson_url + "?name=Test%20Region%201")
        self.assertIsNotNone(self.geojson_cache.get(key_to_clear))

        # 2. Run clear command
        out = io.StringIO()
        call_command(
            "clear_geojson_cache", pattern="*region_geojson*", stdout=out
        )  # Clear region keys
        self.assertIn("Cache cleared with pattern: *region_geojson*", out.getvalue())

        # 3. Verify key is gone
        self.assertIsNone(self.geojson_cache.get(key_to_clear))
