from django.test import SimpleTestCase
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.urls import reverse
from unittest.mock import patch

from sources.greenhouses.router import router as NantesRouter
from sources.greenhouses.urls import urlpatterns as NantesUrlpatterns
from sources.greenhouses.views import (
    CultureAutocompleteView,
    CultureCreateView,
    CultureDetailView,
    CultureModalCreateView,
    CultureModalDeleteView,
    CultureModalUpdateView,
    CulturePrivateListView,
    CulturePublishedListView,
    CultureUpdateView,
    GreenhouseCreateView,
    GreenhouseDetailView,
    GreenhouseGrowthCycleCreateView,
    GreenhouseModalCreateView,
    GreenhouseModalDeleteView,
    GreenhouseModalUpdateView,
    GreenhousePrivateFilterView,
    GreenhousePublishedFilterView,
    GreenhousesPublishedMapView,
    GreenhouseUpdateView,
    GrowthCycleDetailView,
    GrowthCycleModalCreateView,
    GrowthCycleModalDeleteView,
    GrowthCycleUpdateView,
    GrowthTimeStepSetModalUpdateView,
    NantesGreenhousesCatchmentAutocompleteView,
    NantesGreenhousesListFileExportView,
    UpdateGreenhouseGrowthCycleValuesView,
)
from sources.roadside_trees.router import router as HamburgRouter
from sources.roadside_trees.urls import urlpatterns as HamburgUrlpatterns
from sources.roadside_trees.viewsets import HamburgRoadsideTreeViewSet
from sources.roadside_trees.views import (
    HamburgRoadsideTreeCatchmentAutocompleteView,
    HamburgRoadsideTreesListFileExportView,
    RoadsideTreesPublishedMapIframeView,
    RoadsideTreesPublishedMapView,
)
from sources.waste_collection.router import router as WasteCollectionRouter
from sources.waste_collection.urls import urlpatterns as WasteCollectionUrlpatterns
from sources.waste_collection.viewsets import CollectionViewSet, CollectorViewSet
import sources.waste_collection.views as waste_collection_views
from sources.waste_collection.views import CollectionDetailView
from sources.greenhouses.viewsets import NantesGreenhousesViewSet
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
    def test_collection_detail_view_is_owned_by_sources(self):
        self.assertEqual(CollectionDetailView.__module__, "sources.waste_collection.views")


class RoadsideTreesOwnershipAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_viewset_is_owned_by_sources(self):
        self.assertEqual(
            HamburgRoadsideTreeViewSet.__module__,
            "sources.roadside_trees.viewsets",
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

    def test_roadside_tree_views_are_owned_by_sources(self):
        for view in (
            RoadsideTreesPublishedMapView,
            RoadsideTreesPublishedMapIframeView,
            HamburgRoadsideTreesListFileExportView,
            HamburgRoadsideTreeCatchmentAutocompleteView,
        ):
            self.assertEqual(view.__module__, "sources.roadside_trees.views")

    def test_roadside_tree_router_and_urls_are_owned_by_sources(self):
        self.assertTrue(HamburgRouter.registry)
        self.assertTrue(HamburgUrlpatterns)

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


class GreenhousesOwnershipAdapterTestCase(SimpleTestCase):
    def test_greenhouse_viewset_is_owned_by_sources(self):
        self.assertEqual(NantesGreenhousesViewSet.__module__, "sources.greenhouses.viewsets")

    def test_greenhouse_views_are_owned_by_sources(self):
        for view in (
            CultureAutocompleteView,
            CultureCreateView,
            CultureDetailView,
            CultureModalCreateView,
            CultureModalDeleteView,
            CultureModalUpdateView,
            CulturePrivateListView,
            CulturePublishedListView,
            CultureUpdateView,
            GreenhouseCreateView,
            GreenhouseDetailView,
            GreenhouseGrowthCycleCreateView,
            GreenhouseModalCreateView,
            GreenhouseModalDeleteView,
            GreenhouseModalUpdateView,
            GreenhousePrivateFilterView,
            GreenhousePublishedFilterView,
            GreenhousesPublishedMapView,
            GreenhouseUpdateView,
            GrowthCycleDetailView,
            GrowthCycleModalCreateView,
            GrowthCycleModalDeleteView,
            GrowthCycleUpdateView,
            GrowthTimeStepSetModalUpdateView,
            NantesGreenhousesCatchmentAutocompleteView,
            NantesGreenhousesListFileExportView,
            UpdateGreenhouseGrowthCycleValuesView,
        ):
            self.assertEqual(view.__module__, "sources.greenhouses.views")

    def test_greenhouse_router_and_urls_are_owned_by_sources(self):
        self.assertTrue(NantesRouter.registry)
        self.assertTrue(NantesUrlpatterns)


class WasteCollectionOwnershipAdapterTestCase(SimpleTestCase):
    def test_waste_collection_viewsets_are_owned_by_sources(self):
        self.assertEqual(CollectionViewSet.__module__, "sources.waste_collection.viewsets")
        self.assertEqual(CollectorViewSet.__module__, "sources.waste_collection.viewsets")

    def test_waste_collection_views_are_owned_by_sources(self):
        view_names = [
            "CollectionExplorerView",
            "CollectionDiagramView",
            "CollectorPublishedListView",
            "CollectionSystemPublishedListView",
            "WasteCategoryPublishedListView",
            "WasteComponentPublishedListView",
            "FeeSystemPublishedListView",
            "WasteFlyerPublishedFilterView",
            "FrequencyPublishedListView",
            "CollectionPropertyValueCreateView",
            "AggregatedCollectionPropertyValueCreateView",
            "CollectionCatchmentPublishedFilterView",
            "CollectionPublishedListView",
            "CollectionDetailView",
            "CollectionReviewItemDetailView",
            "CollectionListFileExportView",
            "WasteCollectionPublishedMapView",
            "WasteCollectionPrivateMapView",
            "WasteCollectionReviewMapView",
            "WasteCollectionPublishedMapIframeView",
            "CollectionSubmitForReviewView",
            "CollectionWithdrawFromReviewView",
            "CollectionApproveItemView",
            "CollectionRejectItemView",
            "CollectionSubmitForReviewModalView",
            "CollectionWithdrawFromReviewModalView",
            "CollectionApproveItemModalView",
            "CollectionRejectItemModalView",
        ]

        for view_name in view_names:
            self.assertEqual(
                getattr(waste_collection_views, view_name).__module__,
                "sources.waste_collection.views",
            )

    def test_waste_collection_router_and_urls_are_owned_by_sources(self):
        self.assertTrue(WasteCollectionRouter.registry)
        self.assertTrue(WasteCollectionUrlpatterns)
