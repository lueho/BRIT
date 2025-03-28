from django.urls import include, path

from .router import router
from .views import (AttributeCreateView, AttributeDetailView, AttributeModalCreateView, AttributeModalDeleteView,
                    AttributeModalDetailView, AttributeModalUpdateView, AttributePrivateListView,
                    AttributePublishedListView, AttributeUpdateView,
                    CatchmentAutocompleteView, CatchmentCreateDrawCustomView, CatchmentCreateMergeLauView,
                    CatchmentCreateSelectRegionView, CatchmentCreateView, CatchmentDetailView, CatchmentModalDeleteView,
                    CatchmentOptionGeometryAPI, CatchmentPrivateFilterView, CatchmentPublishedFilterView,
                    CatchmentRegionGeometryAPI, CatchmentRegionSummaryAPIView, CatchmentUpdateView,
                    GeoDataSetCreateView, GeoDataSetModalDeleteView, GeoDataSetPrivateFilterView,
                    GeoDataSetPublishedFilterView, GeoDataSetUpdateView, LauRegionOptionsAPI, LocationCreateView,
                    LocationDetailView, LocationModalDeleteView, LocationPrivateListView, LocationPublishedListView,
                    LocationUpdateView,
                    MapsDashboardView, NutsAndLauCatchmentPedigreeAPI, NutsRegionAutocompleteView, NutsRegionMapView,
                    NutsRegionParentsDetailAPI, NutsRegionPedigreeAPI, NutsRegionSummaryAPIView,
                    RegionAttributeValueCreateView, RegionAttributeValueDetailView, RegionAttributeValueModalCreateView,
                    RegionAttributeValueModalDeleteView, RegionAttributeValueModalDetailView,
                    RegionAttributeValueModalUpdateView, RegionAttributeValueUpdateView, RegionAutocompleteView,
                    RegionCreateView, RegionDetailView, RegionMapView, RegionModalDeleteView,
                    RegionOfLauAutocompleteView, RegionPrivateFilterView, RegionPublishedFilterView, RegionUpdateView)

urlpatterns = [
    path('explorer/', MapsDashboardView.as_view(), name='maps-dashboard'),
    path('list/', GeoDataSetPublishedFilterView.as_view(), name='maps_list'),
    path('geodatasets/', GeoDataSetPublishedFilterView.as_view(), name='geodataset-list'),
    path('geodatasets/user/', GeoDataSetPrivateFilterView.as_view(), name='geodataset-list-owned'),
    path('geodatasets/create/', GeoDataSetCreateView.as_view(), name='geodataset-create'),
    path('geodatasets/<int:pk>/update/', GeoDataSetUpdateView.as_view(), name='geodataset-update'),
    path('geodatasets/<int:pk>/delete/', GeoDataSetModalDeleteView.as_view(), name='geodataset-delete-modal'),
    path('attributes/', AttributePublishedListView.as_view(), name='attribute-list'),
    path('attributes/user/', AttributePrivateListView.as_view(), name='attribute-list-owned'),
    path('attributes/create/', AttributeCreateView.as_view(), name='attribute-create'),
    path('attributes/create/modal/', AttributeModalCreateView.as_view(), name='attribute-create-modal'),
    path('attributes/<int:pk>/', AttributeDetailView.as_view(), name='attribute-detail'),
    path('attributes/<int:pk>/modal/', AttributeModalDetailView.as_view(), name='attribute-detail-modal'),
    path('attributes/<int:pk>/update/', AttributeUpdateView.as_view(), name='attribute-update'),
    path('attributes/<int:pk>/update/modal/', AttributeModalUpdateView.as_view(), name='attribute-update-modal'),
    path('attributes/<int:pk>/delete/modal', AttributeModalDeleteView.as_view(), name='attribute-delete-modal'),
    path('attribute_values/create/', RegionAttributeValueCreateView.as_view(), name='regionattributevalue-create'),
    path('attribute_values/create/modal/', RegionAttributeValueModalCreateView.as_view(),
         name='regionattributevalue-create-modal'),
    path('attribute_values/<int:pk>/', RegionAttributeValueDetailView.as_view(), name='regionattributevalue-detail'),
    path('attribute_values/<int:pk>/modal/', RegionAttributeValueModalDetailView.as_view(),
         name='regionattributevalue-detail-modal'),
    path('attribute_values/<int:pk>/update/', RegionAttributeValueUpdateView.as_view(),
         name='regionattributevalue-update'),
    path('attribute_values/<int:pk>/update/modal/', RegionAttributeValueModalUpdateView.as_view(),
         name='regionattributevalue-update-modal'),
    path('attribute_values/<int:pk>/delete/modal', RegionAttributeValueModalDeleteView.as_view(),
         name='regionattributevalue-delete-modal'),
    path('catchments/', CatchmentPublishedFilterView.as_view(), name='catchment-list'),
    path('catchments/user/', CatchmentPrivateFilterView.as_view(), name='catchment-list-owned'),
    path('catchments/create/', CatchmentCreateView.as_view(), name='catchment-create'),
    path('catchments/create/select_region/', CatchmentCreateSelectRegionView.as_view(),
         name='catchment-create-select-region'),
    path('catchments/create/draw_custom/', CatchmentCreateDrawCustomView.as_view(),
         name='catchment-create-draw-custom'),
    path('catchments/create/merge_lau/', CatchmentCreateMergeLauView.as_view(), name='catchment-create-merge-lau'),
    path('catchments/<int:pk>/', CatchmentDetailView.as_view(), name='catchment-detail'),
    path('catchments/<int:pk>/update/', CatchmentUpdateView.as_view(), name='catchment-update'),
    path('catchments/<int:pk>/delete/modal/', CatchmentModalDeleteView.as_view(), name='catchment-delete-modal'),
    path('catchments/autocomplete/', CatchmentAutocompleteView.as_view(), name='catchment-autocomplete'),
    path('catchment_options/data/', CatchmentOptionGeometryAPI.as_view(), name='data.catchment-options'),
    path('regions/', RegionPublishedFilterView.as_view(), name='region-list'),
    path('regions/user/', RegionPrivateFilterView.as_view(), name='region-list-owned'),
    path('regions/create/', RegionCreateView.as_view(), name='region-create'),
    path('regions/<int:pk>/', RegionDetailView.as_view(), name='region-detail'),
    path('regions/<int:pk>/update/', RegionUpdateView.as_view(), name='region-update'),
    path('regions/<int:pk>/delete/modal/', RegionModalDeleteView.as_view(), name='region-delete-modal'),
    path('regions/autocomplete/', RegionAutocompleteView.as_view(), name='region-autocomplete'),
    path('regions/autocomplete/lau/', RegionOfLauAutocompleteView.as_view(), name='region-of-lau-autocomplete'),
    path('regions/map/', RegionMapView.as_view(), name='region-map'),
    path('api/nutsregion/<int:pk>/parents/', NutsRegionParentsDetailAPI.as_view(), name='nutsregion-parents-detail'),
    path('nutsregions/map/', NutsRegionMapView.as_view(), name='NutsRegion'),
    path('nutsregions/summary/', NutsRegionSummaryAPIView.as_view(), name='data.nutsregion-summary'),
    path('nutsregions/options/data/', NutsRegionPedigreeAPI.as_view(), name='data.nuts_region_options'),
    path('nutsregions/autocomplete/', NutsRegionAutocompleteView.as_view(), name='nutsregion-autocomplete'),
    path('lau_options/data/', LauRegionOptionsAPI.as_view(), name='data.lau_region_options'),
    path('nuts_lau_catchment_options/data/', NutsAndLauCatchmentPedigreeAPI.as_view(),
         name='data.nuts_lau_catchment_options'),
    path('catchment_region_geometries/', CatchmentRegionGeometryAPI.as_view(), name='data.catchment_region_geometries'),
    path('catchment_regions_summaries/', CatchmentRegionSummaryAPIView.as_view(),
         name='data.catchment_region_summaries'),
    # TODO: Can case study urls be detected and added automatically?
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
    path('hamburg/', include('case_studies.flexibi_hamburg.urls')),
    path('locations/', LocationPublishedListView.as_view(), name='location-list'),
    path('locations/user/', LocationPrivateListView.as_view(), name='location-list-owned'),
    path('locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('locations/<int:pk>/', LocationDetailView.as_view(), name='location-detail'),
    path('locations/<int:pk>/update/', LocationUpdateView.as_view(), name='location-update'),
    path('locations/<int:pk>/delete/', LocationModalDeleteView.as_view(), name='location-delete-modal'),
    path('api/', include(router.urls)),
]
