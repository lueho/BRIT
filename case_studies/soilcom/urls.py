from django.urls import include, path

from maps.views import CatchmentModalDeleteView
from . import views
from .router import router

urlpatterns = [
    path('', views.CollectionHomeView.as_view(), name='wastecollection-dashboard'),
    path('catchments/<int:pk>/', views.CollectionCatchmentDetailView.as_view(), name='collectioncatchment-detail'),
    path('catchments/<int:pk>/update/', views.CollectionCatchmentUpdateView.as_view(), name='collectioncatchment-update'),
    path('catchments/<int:pk>/delete/modal/', CatchmentModalDeleteView.as_view(), name='collectioncatchment-delete-modal'),
    path('catchments/<int:pk>/add_aggregated_property/', views.CollectionCatchmentAddAggregatedPropertyView.as_view(), name='collectioncatchment-add-aggregatedpropertyvalue'),
    path('collectors/', views.CollectorPublishedListView.as_view(), name='collector-list'),
    path('collectors/user/', views.CollectorPrivateListView.as_view(), name='collector-list-owned'),
    path('collectors/create/', views.CollectorCreateView.as_view(), name='collector-create'),
    path('collectors/create/modal/', views.CollectorModalCreateView.as_view(), name='collector-create-modal'),
    path('collectors/<int:pk>/', views.CollectorDetailView.as_view(), name='collector-detail'),
    path('collectors/<int:pk>/modal/', views.CollectorModalDetailView.as_view(), name='collector-detail-modal'),
    path('collectors/<int:pk>/update/', views.CollectorUpdateView.as_view(), name='collector-update'),
    path('collectors/<int:pk>/update/modal/', views.CollectorModalUpdateView.as_view(), name='collector-update-modal'),
    path('collectors/<int:pk>/delete/modal/', views.CollectorModalDeleteView.as_view(), name='collector-delete-modal'),
    path('collectors/options/', views.CollectorOptions.as_view(), name='collector-options'),
    path('collectors/autocomplete/', views.CollectorAutoCompleteView.as_view(), name='collector-autocomplete'),
    path('collectionsystems/', views.CollectionSystemPublishedListView.as_view(), name='collectionsystem-list'),
    path('collectionsystems/user/', views.CollectionSystemPrivateListView.as_view(),
         name='collectionsystem-list-owned'),
    path('collectionsystems/create/', views.CollectionSystemCreateView.as_view(), name='collectionsystem-create'),
    path('collectionsystems/create/modal/', views.CollectionSystemModalCreateView.as_view(),
         name='collectionsystem-create-modal'),
    path('collectionsystems/<int:pk>/', views.CollectionSystemDetailView.as_view(), name='collectionsystem-detail'),
    path('collectionsystems/<int:pk>/modal/', views.CollectionSystemModalDetailView.as_view(),
         name='collectionsystem-detail-modal'),
    path('collectionsystems/<int:pk>/update/', views.CollectionSystemUpdateView.as_view(),
         name='collectionsystem-update'),
    path('collectionsystems/<int:pk>/update/modal/', views.CollectionSystemModalUpdateView.as_view(),
         name='collectionsystem-update-modal'),
    path('collectionsystems/<int:pk>/delete/modal/', views.CollectionSystemModalDeleteView.as_view(),
         name='collectionsystem-delete-modal'),
    path('collectionsystems/options/', views.CollectionSystemOptions.as_view(), name='collectionsystem-options'),
    path('wastecategories/', views.WasteCategoryPublishedListView.as_view(), name='wastecategory-list'),
    path('wastecategories/user/', views.WasteCategoryPrivateListView.as_view(), name='wastecategory-list-owned'),
    path('wastecategories/create/', views.WasteCategoryCreateView.as_view(), name='wastecategory-create'),
    path('wastecategories/create/modal/', views.WasteCategoryModalCreateView.as_view(),
         name='wastecategory-create-modal'),
    path('wastecategories/<int:pk>/', views.WasteCategoryDetailView.as_view(), name='wastecategory-detail'),
    path('wastecategories/<int:pk>/modal/', views.WasteCategoryModalDetailView.as_view(),
         name='wastecategory-detail-modal'),
    path('wastecategories/<int:pk>/update/', views.WasteCategoryUpdateView.as_view(), name='wastecategory-update'),
    path('wastecategories/<int:pk>/update/modal/', views.WasteCategoryModalUpdateView.as_view(),
         name='wastecategory-update-modal'),
    path('wastecategories/<int:pk>/delete/modal/', views.WasteCategoryModalDeleteView.as_view(),
         name='wastecategory-delete-modal'),
    path('wastecategories/options/', views.WasteCategoryOptions.as_view(), name='wastecategory-options'),
    path('wastecomponents/', views.WasteComponentPublishedListView.as_view(), name='wastecomponent-list'),
    path('wastecomponents/user/', views.WasteComponentPrivateListView.as_view(), name='wastecomponent-list-owned'),
    path('wastecomponents/create/', views.WasteComponentCreateView.as_view(), name='wastecomponent-create'),
    path('wastecomponents/create/modal/', views.WasteComponentModalCreateView.as_view(),
         name='wastecomponent-create-modal'),
    path('wastecomponents/<int:pk>/', views.WasteComponentDetailView.as_view(), name='wastecomponent-detail'),
    path('wastecomponents/<int:pk>/modal/', views.WasteComponentModalDetailView.as_view(),
         name='wastecomponent-detail-modal'),
    path('wastecomponents/<int:pk>/update/', views.WasteComponentUpdateView.as_view(), name='wastecomponent-update'),
    path('wastecomponents/<int:pk>/update/modal/', views.WasteComponentModalUpdateView.as_view(),
         name='wastecomponent-update-modal'),
    path('wastecomponents/<int:pk>/delete/modal/', views.WasteComponentModalDeleteView.as_view(),
         name='wastecomponent-delete-modal'),
    path('frequencies/', views.FrequencyPublishedListView.as_view(), name='collectionfrequency-list'),
    path('frequencies/user/', views.FrequencyPrivateListView.as_view(), name='collectionfrequency-list-owned'),
    path('frequencies/autocomplete/', views.FrequencyAutoCompleteView.as_view(),
         name='collectionfrequency-autocomplete'),
    path('frequencies/create/', views.FrequencyCreateView.as_view(), name='collectionfrequency-create'),
    path('frequencies/<int:pk>/', views.FrequencyDetailView.as_view(), name='collectionfrequency-detail'),
    path('frequencies/<int:pk>/modal/', views.FrequencyModalDetailView.as_view(),
         name='collectionfrequency-detail-modal'),
    path('frequencies/<int:pk>/update/', views.FrequencyUpdateView.as_view(), name='collectionfrequency-update'),
    path('frequencies/<int:pk>/update/modal/', views.FrequencyModalUpdateView.as_view(),
         name='collectionfrequency-update-modal'),
    path('frequencies/<int:pk>/delete/modal/', views.FrequencyModalDeleteView.as_view(),
         name='collectionfrequency-delete-modal'),
    path('frequencies/options/', views.CollectionFrequencyOptions.as_view(), name='collectionfrequency-options'),
    path('properties/create/', views.CollectionPropertyValueCreateView.as_view(),
         name='collectionpropertyvalue-create'),
    path('properties/<int:pk>/', views.CollectionPropertyValueDetailView.as_view(),
         name='collectionpropertyvalue-detail'),
    path('properties/<int:pk>/update/', views.CollectionPropertyValueUpdateView.as_view(),
         name='collectionpropertyvalue-update'),
    path('properties/<int:pk>/delete/modal/', views.CollectionPropertyValueModalDeleteView.as_view(),
         name='collectionpropertyvalue-delete-modal'),
    path('properties/aggregated/create/', views.AggregatedCollectionPropertyValueCreateView.as_view(),
         name='aggregatedcollectionpropertyvalue-create'),
    path('properties/aggregated/<int:pk>/', views.AggregatedCollectionPropertyValueDetailView.as_view(),
         name='aggregatedcollectionpropertyvalue-detail'),
    path('properties/aggregated/<int:pk>/update/', views.AggregatedCollectionPropertyValueUpdateView.as_view(),
         name='aggregatedcollectionpropertyvalue-update'),
    path('properties/aggregated/<int:pk>/delete/modal/',
         views.AggregatedCollectionPropertyValueModalDeleteView.as_view(),
         name='aggregatedcollectionpropertyvalue-delete-modal'),
    path('flyers/', views.WasteFlyerPublishedFilterView.as_view(), name='wasteflyer-list'),
    path('flyers/user/', views.WasteFlyerPrivateFilterView.as_view(), name='wasteflyer-list-owned'),
    path('flyers/create/', views.WasteFlyerCreateView.as_view(), name='wasteflyer-create'),
    path('flyers/create/modal/', views.WasteFlyerModalCreateView.as_view(), name='wasteflyer-create-modal'),
    path('flyers/<int:pk>/', views.WasteFlyerDetailView.as_view(), name='wasteflyer-detail'),
    path('flyers/<int:pk>/modal/', views.WasteFlyerModalDetailView.as_view(), name='wasteflyer-detail-modal'),
    path('flyers/<int:pk>/delete/modal/', views.WasteFlyerModalDeleteView.as_view(), name='wasteflyer-delete-modal'),
    path('flyers/<int:pk>/check_url_in_task/', views.WasteFlyerCheckUrlView.as_view(), name='wasteflyer-check-url'),
    path('flyers/check_url_in_task/<str:task_id>/progress/', views.WasteFlyerCheckUrlProgressView.as_view(),
         name='wasteflyer-check-url-progress'),
    path('flyers/list/check_urls/', views.WasteFlyerListCheckUrlsView.as_view(), name='wasteflyer-list-check-urls'),
    path('flyers/list/check_urls/<str:task_id>/progress/', views.WasteFlyerListCheckUrlsProgressView.as_view(),
         name='wasteflyer-list-check-urls-progress'),
    path('collections/', views.CollectionCurrentPublishedListView.as_view(), name='collection-list'),
    path('collections/user/', views.CollectionCurrentPrivateListView.as_view(), name='collection-list-owned'),
    path('collections/create/', views.CollectionCreateView.as_view(), name='collection-create'),
    path('collections/<int:pk>/', views.CollectionDetailView.as_view(), name='collection-detail'),
    path('collections/<int:pk>/modal/', views.CollectionModalDetailView.as_view(), name='collection-detail-modal'),
    path('collections/<int:pk>/update/', views.CollectionUpdateView.as_view(), name='collection-update'),
    path('collections/<int:pk>/copy/', views.CollectionCopyView.as_view(), name='collection-copy'),
    path('collections/<int:pk>/new_version/', views.CollectionCreateNewVersionView.as_view(),
         name='collection-new-version'),
    path('collections/<int:pk>/delete/modal/', views.CollectionModalDeleteView.as_view(),
         name='collection-delete-modal'),
    path('collections/<int:pk>/add_property/', views.CollectionAddPropertyValueView.as_view(),
         name='collection-add-property'),
    path('collections/<int:pk>/wastesamples/', views.CollectionWasteSamplesView.as_view(),
         name='collection-wastesamples'),
    path('collections/<int:pk>/predecessors/', views.CollectionPredecessorsView.as_view(),
         name='collection-predecessors'),
    path('collections/autocomplete/', views.CollectionAutoCompleteView.as_view(), name='collection-autocomplete'),
    path('collections/map/', views.WasteCollectionMapView.as_view(), name='WasteCollection'),
    path('collections/map/iframe/', views.WasteCollectionMapIframeView.as_view(), name='WasteCollectionIframe'),
    path('catchment_selection/', views.CatchmentSelectView.as_view(), name='catchment-selection'),
    path('api/', include(router.urls)),
    path('collections/export/', views.CollectionListFileExportView.as_view(), name='collection-export'),
]
