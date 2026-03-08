from django.test import SimpleTestCase
from django.urls import reverse
from unittest.mock import patch

import case_studies.soilcom.views as legacy_waste_collection_views
from case_studies.flexibi_hamburg.viewsets import (
    HamburgRoadsideTreeViewSet as LegacyHamburgRoadsideTreeViewSet,
)
from case_studies.flexibi_hamburg.router import router as LegacyHamburgRouter
from case_studies.flexibi_hamburg.urls import urlpatterns as LegacyHamburgUrlpatterns
from case_studies.flexibi_hamburg.views import (
    HamburgRoadsideTreeCatchmentAutocompleteView as LegacyHamburgRoadsideTreeCatchmentAutocompleteView,
    HamburgRoadsideTreesListFileExportView as LegacyHamburgRoadsideTreesListFileExportView,
    RoadsideTreesPublishedMapIframeView as LegacyRoadsideTreesPublishedMapIframeView,
    RoadsideTreesPublishedMapView as LegacyRoadsideTreesPublishedMapView,
)
from case_studies.flexibi_nantes.rounter import router as LegacyNantesRouter
from case_studies.flexibi_nantes.urls import urlpatterns as LegacyNantesUrlpatterns
from case_studies.flexibi_nantes.viewsets import (
    NantesGreenhousesViewSet as LegacyNantesGreenhousesViewSet,
)
from case_studies.flexibi_nantes.views import (
    CultureAutocompleteView as LegacyCultureAutocompleteView,
    CultureCreateView as LegacyCultureCreateView,
    CultureDetailView as LegacyCultureDetailView,
    CultureModalCreateView as LegacyCultureModalCreateView,
    CultureModalDeleteView as LegacyCultureModalDeleteView,
    CultureModalUpdateView as LegacyCultureModalUpdateView,
    CulturePrivateListView as LegacyCulturePrivateListView,
    CulturePublishedListView as LegacyCulturePublishedListView,
    CultureUpdateView as LegacyCultureUpdateView,
    GreenhouseCreateView as LegacyGreenhouseCreateView,
    GreenhouseDetailView as LegacyGreenhouseDetailView,
    GreenhouseGrowthCycleCreateView as LegacyGreenhouseGrowthCycleCreateView,
    GreenhouseModalCreateView as LegacyGreenhouseModalCreateView,
    GreenhouseModalDeleteView as LegacyGreenhouseModalDeleteView,
    GreenhouseModalUpdateView as LegacyGreenhouseModalUpdateView,
    GreenhousePrivateFilterView as LegacyGreenhousePrivateFilterView,
    GreenhousePublishedFilterView as LegacyGreenhousePublishedFilterView,
    GreenhousesPublishedMapView as LegacyGreenhousesPublishedMapView,
    GreenhouseUpdateView as LegacyGreenhouseUpdateView,
    GrowthCycleDetailView as LegacyGrowthCycleDetailView,
    GrowthCycleModalCreateView as LegacyGrowthCycleModalCreateView,
    GrowthCycleModalDeleteView as LegacyGrowthCycleModalDeleteView,
    GrowthCycleUpdateView as LegacyGrowthCycleUpdateView,
    GrowthTimeStepSetModalUpdateView as LegacyGrowthTimeStepSetModalUpdateView,
    NantesGreenhousesCatchmentAutocompleteView as LegacyNantesGreenhousesCatchmentAutocompleteView,
    NantesGreenhousesListFileExportView as LegacyNantesGreenhousesListFileExportView,
    UpdateGreenhouseGrowthCycleValuesView as LegacyUpdateGreenhouseGrowthCycleValuesView,
)
from case_studies.soilcom.router import router as LegacyWasteCollectionRouter
from case_studies.soilcom.urls import urlpatterns as LegacyWasteCollectionUrlpatterns
from case_studies.soilcom.viewsets import (
    CollectionViewSet as LegacyCollectionViewSet,
    CollectorViewSet as LegacyCollectorViewSet,
)
from case_studies.soilcom.views import CollectionDetailView as LegacyCollectionDetailView
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
    def test_collection_detail_view_adapter_reexports_legacy_view(self):
        self.assertIs(CollectionDetailView, LegacyCollectionDetailView)


class RoadsideTreesOwnershipAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_viewset_adapter_reexports_legacy_viewset(self):
        self.assertIs(HamburgRoadsideTreeViewSet, LegacyHamburgRoadsideTreeViewSet)

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


class GreenhousesOwnershipAdapterTestCase(SimpleTestCase):
    def test_greenhouse_viewset_adapter_reexports_legacy_viewset(self):
        self.assertIs(NantesGreenhousesViewSet, LegacyNantesGreenhousesViewSet)

    def test_greenhouse_views_are_owned_by_sources_and_reexported_legacy(self):
        self.assertIs(CultureAutocompleteView, LegacyCultureAutocompleteView)
        self.assertIs(CultureCreateView, LegacyCultureCreateView)
        self.assertIs(CultureDetailView, LegacyCultureDetailView)
        self.assertIs(CultureModalCreateView, LegacyCultureModalCreateView)
        self.assertIs(CultureModalDeleteView, LegacyCultureModalDeleteView)
        self.assertIs(CultureModalUpdateView, LegacyCultureModalUpdateView)
        self.assertIs(CulturePrivateListView, LegacyCulturePrivateListView)
        self.assertIs(CulturePublishedListView, LegacyCulturePublishedListView)
        self.assertIs(CultureUpdateView, LegacyCultureUpdateView)
        self.assertIs(GreenhouseCreateView, LegacyGreenhouseCreateView)
        self.assertIs(GreenhouseDetailView, LegacyGreenhouseDetailView)
        self.assertIs(
            GreenhouseGrowthCycleCreateView,
            LegacyGreenhouseGrowthCycleCreateView,
        )
        self.assertIs(GreenhouseModalCreateView, LegacyGreenhouseModalCreateView)
        self.assertIs(GreenhouseModalDeleteView, LegacyGreenhouseModalDeleteView)
        self.assertIs(GreenhouseModalUpdateView, LegacyGreenhouseModalUpdateView)
        self.assertIs(GreenhousePrivateFilterView, LegacyGreenhousePrivateFilterView)
        self.assertIs(GreenhousePublishedFilterView, LegacyGreenhousePublishedFilterView)
        self.assertIs(GreenhousesPublishedMapView, LegacyGreenhousesPublishedMapView)
        self.assertIs(GreenhouseUpdateView, LegacyGreenhouseUpdateView)
        self.assertIs(GrowthCycleDetailView, LegacyGrowthCycleDetailView)
        self.assertIs(GrowthCycleModalCreateView, LegacyGrowthCycleModalCreateView)
        self.assertIs(GrowthCycleModalDeleteView, LegacyGrowthCycleModalDeleteView)
        self.assertIs(GrowthCycleUpdateView, LegacyGrowthCycleUpdateView)
        self.assertIs(
            GrowthTimeStepSetModalUpdateView,
            LegacyGrowthTimeStepSetModalUpdateView,
        )
        self.assertIs(
            NantesGreenhousesCatchmentAutocompleteView,
            LegacyNantesGreenhousesCatchmentAutocompleteView,
        )
        self.assertIs(
            NantesGreenhousesListFileExportView,
            LegacyNantesGreenhousesListFileExportView,
        )
        self.assertIs(
            UpdateGreenhouseGrowthCycleValuesView,
            LegacyUpdateGreenhouseGrowthCycleValuesView,
        )

    def test_greenhouse_router_and_urls_are_owned_by_sources_and_reexported_legacy(self):
        self.assertIs(NantesRouter, LegacyNantesRouter)
        self.assertIs(NantesUrlpatterns, LegacyNantesUrlpatterns)


class WasteCollectionOwnershipAdapterTestCase(SimpleTestCase):
    def test_waste_collection_viewset_adapters_reexport_legacy_viewsets(self):
        self.assertIs(CollectionViewSet, LegacyCollectionViewSet)
        self.assertIs(CollectorViewSet, LegacyCollectorViewSet)

    def test_waste_collection_views_are_owned_by_sources_and_reexported_legacy(self):
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
            self.assertIs(
                getattr(waste_collection_views, view_name),
                getattr(legacy_waste_collection_views, view_name),
            )

    def test_waste_collection_router_and_urls_are_owned_by_sources_and_reexported_legacy(self):
        self.assertIs(WasteCollectionRouter, LegacyWasteCollectionRouter)
        self.assertIs(WasteCollectionUrlpatterns, LegacyWasteCollectionUrlpatterns)
