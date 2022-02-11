from django.urls import include, path

from .views import (
    CatchmentBrowseView,
    CatchmentCreateView,
    CatchmentGeometryAPI,
    CatchmentOptionGeometryAPI,
    CatchmentUpdateView,
    CatchmentDeleteView,
    CatchmentRegionGeometryAPI,
    MapsListView,
    RegionGeometryAPI,
    NutsMapView,
    NutsRegionAPIView,
    NutsRegionPedigreeAPI,
    LauRegionOptionsAPI,
    NutsAndLauCatchmentPedigreeAPI
)

urlpatterns = [
    path('list/', MapsListView.as_view(), name='maps_list'),
    path('catchments/', CatchmentBrowseView.as_view(), name='catchment_list'),
    path('catchment/create/', CatchmentCreateView.as_view(), name='catchment_definition'),
    path('catchment/create/modal/', CatchmentCreateView.as_view(), name='catchment-create-modal'),
    path('catchments/<int:pk>/update/', CatchmentUpdateView.as_view(), name='catchment_update'),
    path('catchments/<int:pk>/delete/', CatchmentDeleteView.as_view(), name='catchment_delete'),
    path('catchments/data/', RegionGeometryAPI.as_view(), name='data.catchments'),
    path('catchment_options/data/', CatchmentOptionGeometryAPI.as_view(), name='data.catchment-options'),
    path('nuts/map/', NutsMapView.as_view(), name='NutsRegion'),
    path('nuts/data/', NutsRegionAPIView.as_view(), name='data.nuts_regions'),
    path('nuts_options/data/', NutsRegionPedigreeAPI.as_view(), name='data.nuts_region_options'),
    path('lau_options/data/', LauRegionOptionsAPI.as_view(), name='data.lau_region_options'),
    path('nuts_lau_catchment_options/data/', NutsAndLauCatchmentPedigreeAPI.as_view(),
         name='data.nuts_lau_catchment_options'),
    path('region_geometries/', RegionGeometryAPI.as_view(), name='ajax_region_geometries'),
    path('catchment_region_geometries/', CatchmentRegionGeometryAPI.as_view(), name='data.catchment_region_geometries'),
    path('catchment_geometries/', CatchmentGeometryAPI.as_view(), name='ajax_catchment_geometries'),
    # TODO: Can case study urls be detected and added automatically?
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
    path('hamburg/', include('case_studies.flexibi_hamburg.urls')),
]
