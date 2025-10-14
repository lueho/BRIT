from django.urls import include, path

from .router import router
from .views import (
    PropertyCreateView,
    PropertyDetailView,
    PropertyListView,
    PropertyModalDeleteView,
    PropertyUnitOptionsView,
    PropertyUpdateView,
    UnitCreateView,
    UnitDetailView,
    UnitListView,
    UnitModalDeleteView,
    UnitUpdateView,
)

urlpatterns = [
    path("explorer/", PropertiesDashboardView.as_view(), name="properties-dashboard"),
    path("properties/", PropertyListView.as_view(), name="property-list"),
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
        "properties/<int:pk>/propertyunit-options/",
        PropertyUnitOptionsView.as_view(),
        name="property-unit-options",
    ),
    path("propertyunits/", UnitListView.as_view(), name="propertyunit-list"),
    path("propertyunits/create/", UnitCreateView.as_view(), name="propertyunit-create"),
    path(
        "propertyunits/<int:pk>/", UnitDetailView.as_view(), name="propertyunit-detail"
    ),
    path(
        "propertyunits/<int:pk>/update/",
        UnitUpdateView.as_view(),
        name="propertyunit-update",
    ),
    path(
        "propertyunits/<int:pk>/delete/modal/",
        UnitModalDeleteView.as_view(),
        name="propertyunit-delete-modal",
    ),
    path("api/", include(router.urls)),
]
