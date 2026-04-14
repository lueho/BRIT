from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from sources.registry import (
    get_hub_source_domain_plugins,
    get_source_domain_explorer_cards,
    get_source_domain_geojson_cache_warmers,
    get_source_domain_legacy_redirects,
    get_source_domain_map_mounts,
    get_source_domain_plugin,
    get_source_domain_public_mounts,
    get_source_domain_sitemap_items,
)
from sources.roadside_trees.views import HamburgRoadsideTreesListFileExportView
from utils.tests.testcases import ViewWithPermissionsTestCase


class SourcesExplorerViewTestCase(ViewWithPermissionsTestCase):
    url_name = "sources-explorer"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)

    @patch(
        "sources.views.get_source_domain_explorer_cards",
        return_value=(
            {
                "title": "Waste Collection",
                "url_name": "collection-list",
                "description": "Description",
                "image_path": "img/example.png",
                "image_alt": "Example",
                "icon_class": "fas fa-fw fa-recycle",
                "cta_label": "Open list",
                "order": 10,
                "published_count": 13,
            },
        ),
    )
    def test_context_uses_registry_explorer_cards(
        self, mock_get_source_domain_explorer_cards
    ):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["source_domain_explorer_cards"],
            mock_get_source_domain_explorer_cards.return_value,
        )
        mock_get_source_domain_explorer_cards.assert_called_once_with()

    def test_template_renders_plugin_driven_explorer_cards(self):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Household Waste Collection")
        self.assertContains(response, "Greenhouses")
        self.assertContains(response, reverse("collection-list"))
        self.assertContains(response, reverse("greenhouse-list"))


class SourcesListViewTestCase(ViewWithPermissionsTestCase):
    url_name = "sources-list"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def test_get_http_301_redirect_for_anonymous(self):
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("sources-explorer"))

    def test_get_http_301_redirect_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("sources-explorer"))


class SourceDomainHubRoutingTestCase(SimpleTestCase):
    def test_hub_mounts_only_opted_in_source_domain_plugins(self):
        self.assertEqual(
            tuple(plugin.slug for plugin in get_hub_source_domain_plugins()),
            ("roadside_trees",),
        )

    def test_registry_exposes_plugin_declared_legacy_redirect_mounts(self):
        redirects = get_source_domain_legacy_redirects()

        self.assertEqual(len(redirects), 2)
        self.assertEqual(redirects[0].mount_path, "case_studies/hamburg/")
        self.assertEqual(redirects[0].urlconf, "sources.roadside_trees.legacy_urls")
        self.assertEqual(redirects[1].mount_path, "case_studies/hamburg/")
        self.assertEqual(redirects[1].urlconf, "sources.urban_green_spaces.legacy_urls")

    def test_registry_exposes_plugin_declared_map_mounts(self):
        map_mounts = get_source_domain_map_mounts()

        self.assertEqual(len(map_mounts), 3)
        self.assertEqual(map_mounts[0].mount_path, "hamburg/")
        self.assertEqual(map_mounts[0].urlconf, "sources.roadside_trees.urls")
        self.assertEqual(map_mounts[1].mount_path, "hamburg/")
        self.assertEqual(map_mounts[1].urlconf, "sources.urban_green_spaces.urls")
        self.assertEqual(map_mounts[2].mount_path, "nantes/")
        self.assertEqual(map_mounts[2].urlconf, "sources.greenhouses.urls")

    def test_registry_exposes_plugin_declared_public_mounts(self):
        public_mounts = get_source_domain_public_mounts()

        self.assertEqual(len(public_mounts), 2)
        self.assertEqual(public_mounts[0].mount_path, "case_studies/nantes/")
        self.assertEqual(public_mounts[0].urlconf, "sources.greenhouses.urls")
        self.assertEqual(public_mounts[1].mount_path, "waste_collection/")
        self.assertEqual(public_mounts[1].urlconf, "sources.waste_collection.urls")

    def test_registry_exposes_plugin_declared_sitemap_items(self):
        sitemap_items = get_source_domain_sitemap_items()

        self.assertIn("/maps/nantes/greenhouses/export/", sitemap_items)
        self.assertIn("/waste_collection/collections/", sitemap_items)
        self.assertNotIn("/maps/nantes/roadside_trees/export/", sitemap_items)
        self.assertNotIn("/case_studies/nantes/roadside_trees/export/", sitemap_items)

    def test_registry_exposes_plugin_declared_geojson_cache_warmers(self):
        warmers = get_source_domain_geojson_cache_warmers()

        self.assertEqual(
            tuple(slug for slug, _warmer in warmers),
            ("roadside_trees", "waste_collection"),
        )

    def test_registry_keeps_plugins_discoverable_by_slug(self):
        self.assertEqual(get_source_domain_plugin("greenhouses").slug, "greenhouses")
        self.assertEqual(
            get_source_domain_plugin("waste_collection").slug,
            "waste_collection",
        )

    def test_roadside_trees_public_route_remains_mounted_under_sources(self):
        self.assertEqual(
            reverse("HamburgRoadsideTrees"), "/sources/roadside_trees/map/"
        )

    def test_greenhouses_public_route_stays_outside_sources_hub_for_now(self):
        self.assertEqual(
            reverse("greenhouse-list"), "/case_studies/nantes/greenhouses/"
        )

    def test_waste_collection_public_route_stays_outside_sources_hub_for_now(self):
        self.assertEqual(reverse("collection-list"), "/waste_collection/collections/")


class RoadsideTreesPluginIntegrationTestCase(SimpleTestCase):
    def test_roadside_trees_plugin_contract_marks_hub_mount(self):
        plugin = get_source_domain_plugin("roadside_trees")

        self.assertTrue(plugin.mount_in_hub)
        self.assertEqual(plugin.mount_path, "")

    def test_roadside_trees_plugin_exposes_legacy_redirect_metadata(self):
        plugin = get_source_domain_plugin("roadside_trees")

        self.assertIsNotNone(plugin.legacy_redirects)
        self.assertEqual(plugin.legacy_redirects.mount_path, "case_studies/hamburg/")
        self.assertEqual(
            plugin.legacy_redirects.urlconf,
            "sources.roadside_trees.legacy_urls",
        )

    def test_roadside_trees_plugin_exposes_map_mount_metadata(self):
        plugin = get_source_domain_plugin("roadside_trees")

        self.assertIsNotNone(plugin.map_mount)
        self.assertEqual(plugin.map_mount.mount_path, "hamburg/")
        self.assertEqual(plugin.map_mount.urlconf, "sources.roadside_trees.urls")

    def test_roadside_trees_plugin_exposes_geojson_cache_warmer_metadata(self):
        plugin = get_source_domain_plugin("roadside_trees")

        self.assertEqual(
            plugin.geojson_cache_warmer,
            "maps.tasks.warm_roadside_tree_geojson_cache",
        )

    def test_roadside_tree_templates_resolve_from_sources(self):
        self.assertIn(
            "/sources/roadside_trees/templates/",
            get_template("hamburg_roadside_trees_map.html").origin.name,
        )
        self.assertIn(
            "/sources/roadside_trees/templates/",
            get_template("hamburg_roadside_trees_map_iframe.html").origin.name,
        )

    def test_roadside_tree_static_assets_resolve_from_sources(self):
        self.assertIn(
            "/sources/roadside_trees/static/",
            finders.find("js/hamburg_roadsidetree_map.min.js"),
        )

    def test_roadside_tree_export_view_uses_sources_model_label(self):
        self.assertEqual(
            HamburgRoadsideTreesListFileExportView.model_label,
            "roadside_trees.HamburgRoadsideTrees",
        )

    def test_legacy_hamburg_urls_redirect_to_sources(self):
        response = self.client.get(
            "/case_studies/hamburg/roadside_trees/map/",
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/sources/roadside_trees/map/")

    def test_legacy_hamburg_api_urls_redirect_to_sources(self):
        response = self.client.get(
            "/case_studies/hamburg/api/hamburg_roadside_trees/",
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/sources/api/hamburg_roadside_trees/",
        )


class UrbanGreenSpacesPluginIntegrationTestCase(SimpleTestCase):
    def test_urban_green_spaces_plugin_keeps_current_public_entry_point(self):
        self.assertEqual(reverse("HamburgGreenAreas"), "/maps/hamburg/green_areas/map/")

    def test_urban_green_spaces_plugin_stays_outside_sources_hub_for_now(self):
        plugin = get_source_domain_plugin("urban_green_spaces")

        self.assertFalse(plugin.mount_in_hub)

    def test_urban_green_spaces_plugin_exposes_map_mount_metadata(self):
        plugin = get_source_domain_plugin("urban_green_spaces")

        self.assertIsNotNone(plugin.map_mount)
        self.assertEqual(plugin.map_mount.mount_path, "hamburg/")
        self.assertEqual(plugin.map_mount.urlconf, "sources.urban_green_spaces.urls")

    def test_urban_green_spaces_plugin_exposes_legacy_redirect_metadata(self):
        plugin = get_source_domain_plugin("urban_green_spaces")

        self.assertIsNotNone(plugin.legacy_redirects)
        self.assertEqual(plugin.legacy_redirects.mount_path, "case_studies/hamburg/")
        self.assertEqual(
            plugin.legacy_redirects.urlconf,
            "sources.urban_green_spaces.legacy_urls",
        )

    def test_legacy_hamburg_green_areas_url_redirects_to_maps(self):
        response = self.client.get(
            "/case_studies/hamburg/green_areas/map/",
            follow=False,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/maps/hamburg/green_areas/map/")


class GreenhousesPluginIntegrationTestCase(SimpleTestCase):
    def test_greenhouses_plugin_exposes_published_count_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertEqual(
            plugin.published_count_getter,
            "sources.greenhouses.selectors.published_greenhouse_count",
        )

    def test_greenhouses_plugin_exposes_explorer_card_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertIsNotNone(plugin.explorer_card)
        self.assertEqual(plugin.explorer_card.title, "Greenhouses")
        self.assertEqual(plugin.explorer_card.url_name, "greenhouse-list")

    def test_greenhouses_plugin_keeps_current_public_entry_point(self):
        self.assertEqual(
            reverse("greenhouse-list"), "/case_studies/nantes/greenhouses/"
        )

    def test_greenhouses_plugin_keeps_current_maps_route_mounted(self):
        self.assertEqual(
            resolve("/maps/nantes/greenhouses/map/").url_name,
            "NantesGreenhouses",
        )

    def test_greenhouses_plugin_exposes_map_mount_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertIsNotNone(plugin.map_mount)
        self.assertEqual(plugin.map_mount.mount_path, "nantes/")
        self.assertEqual(plugin.map_mount.urlconf, "sources.greenhouses.urls")

    def test_greenhouses_plugin_exposes_sitemap_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertIn("/maps/nantes/greenhouses/export/", plugin.sitemap_items)
        self.assertIn("/case_studies/nantes/greenhouses/export/", plugin.sitemap_items)
        self.assertNotIn("/maps/nantes/roadside_trees/export/", plugin.sitemap_items)

    def test_greenhouses_plugin_exposes_public_mount_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertIsNotNone(plugin.public_mount)
        self.assertEqual(plugin.public_mount.mount_path, "case_studies/nantes/")
        self.assertEqual(plugin.public_mount.urlconf, "sources.greenhouses.urls")


class WasteCollectionPluginIntegrationTestCase(SimpleTestCase):
    def test_waste_collection_plugin_exposes_published_count_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertEqual(
            plugin.published_count_getter,
            "sources.waste_collection.selectors.published_collection_count",
        )

    def test_waste_collection_plugin_exposes_explorer_card_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertIsNotNone(plugin.explorer_card)
        self.assertEqual(plugin.explorer_card.title, "Household Waste Collection")
        self.assertEqual(plugin.explorer_card.url_name, "collection-list")

    def test_waste_collection_plugin_keeps_current_public_entry_point(self):
        self.assertEqual(reverse("collection-list"), "/waste_collection/collections/")

    def test_waste_collection_plugin_exposes_public_mount_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertIsNotNone(plugin.public_mount)
        self.assertEqual(plugin.public_mount.mount_path, "waste_collection/")
        self.assertEqual(plugin.public_mount.urlconf, "sources.waste_collection.urls")

    def test_waste_collection_plugin_exposes_sitemap_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertIn("/waste_collection/collections/", plugin.sitemap_items)
        self.assertIn("/waste_collection/collections/export/", plugin.sitemap_items)

    def test_waste_collection_plugin_exposes_geojson_cache_warmer_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertEqual(
            plugin.geojson_cache_warmer,
            "maps.tasks.warm_collection_geojson_cache",
        )


class SourceDomainExplorerCardRegistryTestCase(SimpleTestCase):
    @patch(
        "sources.registry.SourceDomainPlugin.get_published_count",
        side_effect=[7, 13],
    )
    def test_registry_returns_sorted_explorer_cards_with_counts(self, _mock_count):
        cards = get_source_domain_explorer_cards()

        self.assertEqual(
            [card["slug"] for card in cards], ["waste_collection", "greenhouses"]
        )
        self.assertEqual(cards[0]["title"], "Household Waste Collection")
        self.assertEqual(cards[1]["title"], "Greenhouses")
        self.assertEqual(cards[0]["published_count"], 13)
        self.assertEqual(cards[1]["published_count"], 7)
