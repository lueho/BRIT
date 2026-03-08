from django.test import SimpleTestCase
from django.urls import reverse
from unittest.mock import patch

from case_studies.flexibi_hamburg.router import router as LegacyHamburgRouter
from case_studies.flexibi_hamburg.urls import urlpatterns as LegacyHamburgUrlpatterns
from case_studies.flexibi_hamburg.views import (
    HamburgRoadsideTreeCatchmentAutocompleteView as LegacyHamburgRoadsideTreeCatchmentAutocompleteView,
    HamburgRoadsideTreesListFileExportView as LegacyHamburgRoadsideTreesListFileExportView,
    RoadsideTreesPublishedMapIframeView as LegacyRoadsideTreesPublishedMapIframeView,
    RoadsideTreesPublishedMapView as LegacyRoadsideTreesPublishedMapView,
)
from case_studies.soilcom.views import CollectionDetailView as LegacyCollectionDetailView
from sources.roadside_trees.router import router as HamburgRouter
from sources.roadside_trees.urls import urlpatterns as HamburgUrlpatterns
from sources.roadside_trees.views import (
    HamburgRoadsideTreeCatchmentAutocompleteView,
    HamburgRoadsideTreesListFileExportView,
    RoadsideTreesPublishedMapIframeView,
    RoadsideTreesPublishedMapView,
)
from sources.waste_collection.views import CollectionDetailView
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

    @patch("sources.views.published_greenhouse_count", return_value=7)
    @patch("sources.views.published_collection_count", return_value=13)
    def test_context_uses_domain_selector_counts(
        self, mock_collection_count, mock_greenhouse_count
    ):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["collection_count"], 13)
        self.assertEqual(response.context["greenhouse_count"], 7)
        mock_collection_count.assert_called_once_with()
        mock_greenhouse_count.assert_called_once_with()


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


class WasteCollectionViewAdapterTestCase(ViewWithPermissionsTestCase):
    def test_collection_detail_view_adapter_reexports_legacy_view(self):
        self.assertIs(CollectionDetailView, LegacyCollectionDetailView)


class RoadsideTreesOwnershipAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_views_are_owned_by_sources_and_reexported_legacy(self):
        self.assertIs(RoadsideTreesPublishedMapView, LegacyRoadsideTreesPublishedMapView)
        self.assertIs(
            RoadsideTreesPublishedMapIframeView,
            LegacyRoadsideTreesPublishedMapIframeView,
        )
        self.assertIs(
            HamburgRoadsideTreesListFileExportView,
            LegacyHamburgRoadsideTreesListFileExportView,
        )
        self.assertIs(
            HamburgRoadsideTreeCatchmentAutocompleteView,
            LegacyHamburgRoadsideTreeCatchmentAutocompleteView,
        )

    def test_roadside_tree_router_and_urls_are_owned_by_sources_and_reexported_legacy(self):
        self.assertIs(HamburgRouter, LegacyHamburgRouter)
        self.assertIs(HamburgUrlpatterns, LegacyHamburgUrlpatterns)
