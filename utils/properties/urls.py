from django.urls import include, path

from .router import router
from .views import (
    PropertiesDashboardView,
    PropertyCreateView,
    PropertyDetailView,
    PropertyModalDeleteView,
    PropertyPrivateListView,
    PropertyPublishedListView,
    PropertyUnitOptionsView,
    PropertyUpdateView,
    UnitCreateView,
    UnitDetailView,
    UnitModalDeleteView,
    UnitPrivateListView,
    UnitPublishedListView,
    UnitUpdateView,
)

urlpatterns = [
    path("explorer/", PropertiesDashboardView.as_view(), name="properties-dashboard"),
    path("properties/", PropertyPublishedListView.as_view(), name="property-list"),
    path(
        "properties/user/",
        PropertyPrivateListView.as_view(),
        name="property-list-owned",
    ),
    path("properties/create/", PropertyCreateView.as_view(), name="property-create"),
    path("properties/<int:pk>/", PropertyDetailView.as_view(), name="property-detail"),
    path(
        "properties/<int:pk>/update/",
        PropertyUpdateView.as_view(),
        name="property-update",
    ),
    path(
        "properties/<int:pk>/delete/modal/",
        PropertyModalDeleteView.as_view(),
        name="property-delete-modal",
    ),
    path(
        "properties/<int:pk>/unit-options/",
        PropertyUnitOptionsView.as_view(),
        name="property-unit-options",
    ),
    path("units/", UnitPublishedListView.as_view(), name="unit-list"),
    path("units/user/", UnitPrivateListView.as_view(), name="unit-list-owned"),
    path("units/create/", UnitCreateView.as_view(), name="unit-create"),
    path("units/<int:pk>/", UnitDetailView.as_view(), name="unit-detail"),
    path("units/<int:pk>/update/", UnitUpdateView.as_view(), name="unit-update"),
    path(
        "units/<int:pk>/delete/modal/",
        UnitModalDeleteView.as_view(),
        name="unit-delete-modal",
    ),
    path("api/", include(router.urls)),
]
