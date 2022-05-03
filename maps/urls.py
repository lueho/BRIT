from django.urls import include, path

from .views import (
    AttributeListView,
    AttributeCreateView,
    AttributeModalCreateView,
    AttributeDetailView,
    AttributeModalDetailView,
    AttributeUpdateView,
    AttributeModalUpdateView,
    AttributeModalDeleteView,
    RegionAttributeValueListView,
    RegionAttributeValueCreateView,
    RegionAttributeValueModalCreateView,
    RegionAttributeValueDetailView,
    RegionAttributeValueModalDetailView,
    RegionAttributeValueUpdateView,
    RegionAttributeValueModalUpdateView,
    RegionAttributeValueModalDeleteView,
    CatchmentBrowseView,
    CatchmentCreateView,
    CatchmentGeometryAPI,
    CatchmentOptionGeometryAPI,
    CatchmentUpdateView,
    CatchmentDeleteView,
    CatchmentRegionGeometryAPI,
    CatchmentRegionSummaryAPIView,
    MapsListView,
    RegionGeometryAPI,
    NutsRegionMapView,
    NutsRegionAPIView,
    NutsRegionSummaryAPIView,
    NutsRegionPedigreeAPI,
    LauRegionOptionsAPI,
    NutsAndLauCatchmentPedigreeAPI
)

urlpatterns = [
    path('list/', MapsListView.as_view(), name='maps_list'),
    path('attributes/', AttributeListView.as_view(), name='attribute-list'),
    path('attributes/create/', AttributeCreateView.as_view(), name='attribute-create'),
    path('attributes/create/modal/', AttributeModalCreateView.as_view(), name='attribute-create-modal'),
    path('attributes/<int:pk>/', AttributeDetailView.as_view(), name='attribute-detail'),
    path('attributes/<int:pk>/modal/', AttributeModalDetailView.as_view(), name='attribute-detail-modal'),
    path('attributes/<int:pk>/update/', AttributeUpdateView.as_view(), name='attribute-update'),
    path('attributes/<int:pk>/update/modal/', AttributeModalUpdateView.as_view(), name='attribute-update-modal'),
    path('attributes/<int:pk>/delete/modal', AttributeModalDeleteView.as_view(), name='attribute-delete-modal'),
    path('attribute_values/', RegionAttributeValueListView.as_view(), name='regionattributevalue-list'),
    path('attribute_values/create/', RegionAttributeValueCreateView.as_view(), name='regionattributevalue-create'),
    path('attribute_values/create/modal/', RegionAttributeValueModalCreateView.as_view(), name='regionattributevalue-create-modal'),
    path('attribute_values/<int:pk>/', RegionAttributeValueDetailView.as_view(), name='regionattributevalue-detail'),
    path('attribute_values/<int:pk>/modal/', RegionAttributeValueModalDetailView.as_view(), name='regionattributevalue-detail-modal'),
    path('attribute_values/<int:pk>/update/', RegionAttributeValueUpdateView.as_view(), name='regionattributevalue-update'),
    path('attribute_values/<int:pk>/update/modal/', RegionAttributeValueModalUpdateView.as_view(), name='regionattributevalue-update-modal'),
    path('attribute_values/<int:pk>/delete/modal', RegionAttributeValueModalDeleteView.as_view(), name='regionattributevalue-delete-modal'),
    path('catchments/', CatchmentBrowseView.as_view(), name='catchment_list'),
    path('catchment/create/', CatchmentCreateView.as_view(), name='catchment_definition'),
    path('catchment/create/modal/', CatchmentCreateView.as_view(), name='catchment-create-modal'),
    path('catchments/<int:pk>/update/', CatchmentUpdateView.as_view(), name='catchment_update'),
    path('catchments/<int:pk>/delete/', CatchmentDeleteView.as_view(), name='catchment_delete'),
    path('catchments/data/', RegionGeometryAPI.as_view(), name='data.catchments'),
    path('catchment_options/data/', CatchmentOptionGeometryAPI.as_view(), name='data.catchment-options'),
    path('nutsregions/map/', NutsRegionMapView.as_view(), name='NutsRegion'),
    path('nutsregions/data/', NutsRegionAPIView.as_view(), name='data.nutsregion'),
    path('nutsregions/summary/', NutsRegionSummaryAPIView.as_view(), name='data.nutsregion-summary'),
    path('nutsregions/options/data/', NutsRegionPedigreeAPI.as_view(), name='data.nuts_region_options'),
    path('lau_options/data/', LauRegionOptionsAPI.as_view(), name='data.lau_region_options'),
    path('nuts_lau_catchment_options/data/', NutsAndLauCatchmentPedigreeAPI.as_view(),
         name='data.nuts_lau_catchment_options'),
    path('region_geometries/', RegionGeometryAPI.as_view(), name='ajax_region_geometries'),
    path('catchment_region_geometries/', CatchmentRegionGeometryAPI.as_view(), name='data.catchment_region_geometries'),
    path('catchment_regions_summaries/', CatchmentRegionSummaryAPIView.as_view(), name='data.catchment_region_summaries'),
    path('catchment_geometries/', CatchmentGeometryAPI.as_view(), name='ajax_catchment_geometries'),
    # TODO: Can case study urls be detected and added automatically?
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
    path('hamburg/', include('case_studies.flexibi_hamburg.urls')),
]
