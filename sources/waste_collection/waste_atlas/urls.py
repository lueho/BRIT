from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from .pages import MAP_PAGES
from .router import router
from .views import (
    AtlasChangeMapView,
    AtlasMapView,
    EuropeBiowasteCollectionAmountMapView,
    EuropeDataCoverageMapIframeView,
    EuropeDataCoverageMapView,
    WasteAtlasChangeMapOverviewView,
    WasteAtlasDataConflictsOverviewView,
    WasteAtlasMapConfigurationListView,
    WasteAtlasMapConfigurationUpdateView,
    WasteAtlasOverviewView,
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "map/",
        WasteAtlasOverviewView.as_view(),
        name="waste-atlas-overview",
    ),
    path(
        "map/changes/",
        WasteAtlasChangeMapOverviewView.as_view(),
        name="waste-atlas-change-map-overview",
    ),
    path(
        "map/data-conflicts/",
        WasteAtlasDataConflictsOverviewView.as_view(),
        name="waste-atlas-data-conflicts-overview",
    ),
    path(
        "map/configurations/",
        WasteAtlasMapConfigurationListView.as_view(),
        name="waste-atlas-map-configuration-list",
    ),
    path(
        "map/configurations/<slug:key>/",
        WasteAtlasMapConfigurationUpdateView.as_view(),
        name="waste-atlas-map-configuration-update",
    ),
    path(
        "map/changes/<str:map_set>/<str:theme>/",
        AtlasChangeMapView.as_view(),
        name="waste-atlas-change-map",
    ),
    # Legacy URL of the formerly hand-built Germany change map
    path(
        "map/germany/collection-system-change/",
        RedirectView.as_view(
            url=reverse_lazy(
                "waste-atlas-change-map", args=["DE", "collection_system"]
            ),
            query_string=True,
        ),
        name="waste-atlas-germany-collection-system-change-map",
    ),
    path(
        "map/europe-data-coverage/",
        EuropeDataCoverageMapView.as_view(),
        name="waste-atlas-europe-data-coverage-map",
    ),
    path(
        "map/europe-data-coverage/iframe/",
        EuropeDataCoverageMapIframeView.as_view(),
        name="waste-atlas-europe-data-coverage-map-iframe",
    ),
    path(
        "map/europe-biowaste-collection-amount/",
        EuropeBiowasteCollectionAmountMapView.as_view(),
        name="waste-atlas-europe-biowaste-collection-amount-map",
    ),
]

urlpatterns += [
    path(page["path"], AtlasMapView.as_view(page=page), name=page["name"])
    for page in MAP_PAGES
]
