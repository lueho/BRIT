from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import reverse

from sources.registry import (
    get_hub_source_domain_plugins,
    get_source_domain_explorer_cards,
    get_source_domain_legacy_redirects,
    get_source_domain_plugin,
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
        "sources.views.get_explorer_context",
        return_value={"collection_count": 13, "greenhouse_count": 7},
    )
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
    def test_context_uses_registry_explorer_context(
        self, mock_get_source_domain_explorer_cards, mock_get_explorer_context
    ):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["collection_count"], 13)
        self.assertEqual(response.context["greenhouse_count"], 7)
        self.assertEqual(
            response.context["source_domain_explorer_cards"],
            mock_get_source_domain_explorer_cards.return_value,
        )
        mock_get_explorer_context.assert_called_once_with()
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

    def test_get_http_301_redirect_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 301)


class SourceDomainHubRoutingTestCase(SimpleTestCase):
    def test_hub_mounts_only_opted_in_source_domain_plugins(self):
        self.assertEqual(
            tuple(plugin.slug for plugin in get_hub_source_domain_plugins()),
            ("roadside_trees",),
        )

    def test_registry_exposes_plugin_declared_legacy_redirect_mounts(self):
        redirects = get_source_domain_legacy_redirects()

        self.assertEqual(len(redirects), 1)
        self.assertEqual(redirects[0].mount_path, "case_studies/hamburg/")
        self.assertEqual(redirects[0].urlconf, "sources.roadside_trees.legacy_urls")

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


class GreenhousesPluginIntegrationTestCase(SimpleTestCase):
    def test_greenhouses_plugin_exposes_explorer_counter_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")

        self.assertEqual(plugin.explorer_context_var, "greenhouse_count")
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


class WasteCollectionPluginIntegrationTestCase(SimpleTestCase):
    def test_waste_collection_plugin_exposes_explorer_counter_metadata(self):
        plugin = get_source_domain_plugin("waste_collection")

        self.assertEqual(plugin.explorer_context_var, "collection_count")
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
