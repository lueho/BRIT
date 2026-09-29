import json

from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.waste_atlas.models import WasteAtlasMapConfiguration

OLD_PREFIX = "/waste_collection/api/waste-atlas/"
NEW_PREFIX = "/waste_collection/waste-atlas/"
NEW_API_PREFIX = f"{NEW_PREFIX}api/"


class WasteAtlasRoutingTests(TestCase):
    def test_pages_live_under_the_atlas_prefix(self):
        self.assertEqual(reverse("waste-atlas-overview"), f"{NEW_PREFIX}map/")
        self.assertEqual(
            reverse("waste-atlas-change-map", args=["DE", "collection_system"]),
            f"{NEW_PREFIX}map/changes/DE/collection_system/",
        )

    def test_data_api_lives_under_the_atlas_api_prefix(self):
        self.assertEqual(
            reverse("api-waste-atlas-catchment-geojson"),
            f"{NEW_API_PREFIX}catchment/geojson/",
        )

    def test_atlas_root_redirects_to_the_map_overview(self):
        response = self.client.get(NEW_PREFIX)
        self.assertRedirects(
            response, reverse("waste-atlas-overview"), fetch_redirect_response=False
        )


class WasteAtlasLegacyRedirectTests(TestCase):
    def assertPermanentRedirect(self, old, new):
        response = self.client.get(old)
        self.assertEqual(response.status_code, 301, old)
        self.assertEqual(response["Location"], new, old)

    def test_old_map_pages_redirect_and_keep_the_query_string(self):
        self.assertPermanentRedirect(
            f"{OLD_PREFIX}map/germany/collection-system/?year=2023&scope=mine",
            f"{NEW_PREFIX}map/germany/collection-system/?year=2023&scope=mine",
        )
        self.assertPermanentRedirect(f"{OLD_PREFIX}map/", f"{NEW_PREFIX}map/")

    def test_old_data_endpoints_redirect_to_the_api_prefix(self):
        self.assertPermanentRedirect(
            f"{OLD_PREFIX}collection-system/?country=DE&year=2024",
            f"{NEW_API_PREFIX}collection-system/?country=DE&year=2024",
        )
        self.assertPermanentRedirect(
            f"{OLD_PREFIX}catchment/geojson/?country=DE",
            f"{NEW_API_PREFIX}catchment/geojson/?country=DE",
        )
        self.assertPermanentRedirect(OLD_PREFIX, NEW_API_PREFIX)

    def test_old_embeddable_iframe_url_redirects(self):
        self.assertPermanentRedirect(
            f"{OLD_PREFIX}map/europe-data-coverage/iframe/",
            f"{NEW_PREFIX}map/europe-data-coverage/iframe/",
        )


class StoredMapConfigurationUrlTests(TestCase):
    def test_stored_configurations_point_at_the_new_api_prefix(self):
        configurations = list(WasteAtlasMapConfiguration.objects.all())
        self.assertTrue(configurations)
        for configuration in configurations:
            serialized = json.dumps(configuration.configuration)
            self.assertNotIn(OLD_PREFIX, serialized, configuration.key)

    def test_stored_data_urls_resolve_to_the_new_api(self):
        configuration = WasteAtlasMapConfiguration.objects.exclude(
            configuration__dataUrl__isnull=True
        ).first()
        self.assertTrue(
            configuration.configuration["dataUrl"].startswith(NEW_API_PREFIX)
        )
