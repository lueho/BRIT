from django.urls import include, path

from .pages import MAP_PAGES
from .router import router
from .views import (
    AtlasChangeMapView,
    AtlasMapView,
    EuropeBiowasteCollectionAmountMapView,
    EuropeDataCoverageMapIframeView,
    EuropeDataCoverageMapView,
    WasteAtlasChangeMapOverviewView,
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
    path(
        page["path"],
        (AtlasChangeMapView if page.get("change") else AtlasMapView).as_view(page=page),
        name=page["name"],
    )
    for page in MAP_PAGES
]
