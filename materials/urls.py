from django.urls import include, path

from . import views
from .router import router

urlpatterns = [
    path('', views.MaterialsDashboardView.as_view(), name='materials-dashboard'),
    path('list/', views.MaterialListView.as_view(), name='material-list'),
    path('create/', views.MaterialCreateView.as_view(), name='material-create'),
    path('create/modal/', views.MaterialModalCreateView.as_view(), name='material-create-modal'),
    path('<int:pk>/', views.MaterialDetailView.as_view(), name='material-detail'),
    path('<int:pk>/modal/', views.MaterialModalDetailView.as_view(), name='material-detail-modal'),
    path('<int:pk>/update/', views.MaterialUpdateView.as_view(), name='material-update'),
    path('<int:pk>/update/modal/', views.MaterialModalUpdateView.as_view(), name='material-update-modal'),
    path('<int:pk>/delete/', views.MaterialModalDeleteView.as_view(), name='material-delete-modal'),
    path('autocomplete/', views.MaterialAutocompleteView.as_view(), name='material-autocomplete'),
    path('sample_series/', views.PublishedSampleSeriesListView.as_view(), name='sampleseries-list'),
    path('sample_series/autocomplete/', views.SampleSeriesAutoCompleteView.as_view(), name='sampleseries-autocomplete'),
    path('sample_series/featured', views.FeaturedMaterialListView.as_view(), name='sampleseries-list-featured'),
    path('sample_series/user/', views.UserOwnedSampleSeriesListView.as_view(), name='sampleseries-list-owned'),
    path('sample_series/create/', views.SampleSeriesCreateView.as_view(), name='sampleseries-create'),
    path('sample_series/create/modal', views.SampleSeriesModalCreateView.as_view(), name='sampleseries-create-modal'),
    path('sample_series/<int:pk>/', views.SampleSeriesDetailView.as_view(), name='sampleseries-detail'),
    path('sample_series/<int:pk>/modal/', views.SampleSeriesModalDetailView.as_view(), name='sampleseries-detail-modal'),
    path('sample_series/<int:pk>/update/', views.SampleSeriesUpdateView.as_view(), name='sampleseries-update'),
    path('sample_series/<int:pk>/update/modal/', views.SampleSeriesModalUpdateView.as_view(), name='sampleseries-update-modal'),
    path('sample_series/<int:pk>/delete/modal/', views.SampleSeriesModalDeleteView.as_view(), name='sampleseries-delete-modal'),
    path('sample_series/<int:pk>/add_composition/', views.AddCompositionView.as_view(), name='sampleseries-add-composition'),
    path('sample_series/<int:pk>/add_distribution/modal/', views.SampleSeriesModalAddDistributionView.as_view(), name='sampleseries-add-distribution-modal'),
    path('sample_series/<int:pk>/duplicate/', views.SampleSeriesCreateDuplicateView.as_view(), name='sampleseries-duplicate'),
    path('sample_series/<int:pk>/duplicate/modal/', views.SampleSeriesModalCreateDuplicateView.as_view(), name='sampleseries-duplicate-modal'),
    path('samples/', views.PublishedSampleListView.as_view(), name='sample-list'),
    path('samples/autocomplete/', views.SampleAutoCompleteView.as_view(), name='sample-autocomplete'),
    path('samples/autocomplete/published/', views.PublishedSampleAutoCompleteView.as_view(), name='sample-autocomplete-published'),
    path('samples/autocomplete/owned/', views.UserOwnedSampleAutoCompleteView.as_view(), name='sample-autocomplete-owned'),
    path('samples/featured', views.FeaturedSampleListView.as_view(), name='sample-list-featured'),
    path('samples/user/', views.UserOwnedSampleListView.as_view(), name='sample-list-owned'),
    path('samples/create/', views.SampleCreateView.as_view(), name='sample-create'),
    path('samples/<int:pk>/', views.SampleDetailView.as_view(), name='sample-detail'),
    path('samples/<int:pk>/update/', views.SampleUpdateView.as_view(), name='sample-update'),
    path('samples/<int:pk>/delete/modal/', views.SampleModalDeleteView.as_view(), name='sample-delete-modal'),
    path('samples/<int:pk>/composition/add/', views.SampleAddCompositionView.as_view(), name='sample-add-composition'),
    path('samples/<int:pk>/add_property', views.SampleAddPropertyView.as_view(), name='sample-add-property'),
    path('samples/<int:pk>/add_property/modal/', views.SampleModalAddPropertyView.as_view(), name='sample-add-property-modal'),
    path('samples/<int:pk>/duplicate/', views.SampleCreateDuplicateView.as_view(), name='sample-duplicate'),
    path('categories/', views.MaterialCategoryListView.as_view(), name='materialcategory-list'),
    path('categories/create/', views.MaterialCategoryCreateView.as_view(), name='materialcategory-create'),
    path('categories/create/modal/', views.MaterialCategoryCreateView.as_view(), name='materialcategory-create-modal'),
    path('categories/<int:pk>/', views.MaterialCategoryDetailView.as_view(), name='materialcategory-detail'),
    path('categories/<int:pk>/modal/', views.MaterialCategoryModalDetailView.as_view(), name='materialcategory-detail-modal'),
    path('categories/<int:pk>/update/', views.MaterialCategoryUpdateView.as_view(), name='materialcategory-update'),
    path('categories/<int:pk>/update/modal/', views.MaterialCategoryModalUpdateView.as_view(), name='materialcategory-update-modal'),
    path('categories/<int:pk>/delete/modal/', views.MaterialCategoryModalDeleteView.as_view(), name='materialcategory-delete-modal'),
    path('components/', views.ComponentListView.as_view(), name='materialcomponent-list'),
    path('components/create/', views.ComponentCreateView.as_view(), name='materialcomponent-create'),
    path('components/create/modal', views.ComponentModalCreateView.as_view(), name='materialcomponent-create-modal'),
    path('components/<int:pk>/', views.ComponentDetailView.as_view(), name='materialcomponent-detail'),
    path('components/<int:pk>/modal/', views.ComponentModalDetailView.as_view(), name='materialcomponent-detail-modal'),
    path('components/<int:pk>/update/', views.ComponentUpdateView.as_view(), name='materialcomponent-update'),
    path('components/<int:pk>/update/modal/', views.ComponentUpdateView.as_view(), name='materialcomponent-update-modal'),
    path('components/<int:pk>/delete/modal/', views.ComponentModalDeleteView.as_view(), name='materialcomponent-delete-modal'),
    path('componentgroups/', views.ComponentGroupListView.as_view(), name='materialcomponentgroup-list'),
    path('componentgroups/create/', views.ComponentGroupCreateView.as_view(), name='materialcomponentgroup-create'),
    path('componentgroups/create/modal/', views.ComponentGroupModalCreateView.as_view(), name='materialcomponentgroup-create-modal'),
    path('componentgroups/<int:pk>/', views.ComponentGroupDetailView.as_view(), name='materialcomponentgroup-detail'),
    path('componentgroups/<int:pk>/modal/', views.ComponentGroupModalDetailView.as_view(), name='materialcomponentgroup-detail-modal'),
    path('componentgroups/<int:pk>/update/', views.ComponentGroupUpdateView.as_view(), name='materialcomponentgroup-update'),
    path('componentgroups/<int:pk>/update/modal/', views.ComponentGroupModalUpdateView.as_view(), name='materialcomponentgroup-update-modal'),
    path('componentgroups/<int:pk>/delete/modal/', views.ComponentGroupModalDeleteView.as_view(), name='materialcomponentgroup-delete-modal'),
    path('properties/', views.MaterialPropertyListView.as_view(), name='materialproperty-list'),
    path('properties/create/', views.MaterialPropertyCreateView.as_view(), name='materialproperty-create'),
    path('properties/create/modal/', views.MaterialPropertyModalCreateView.as_view(), name='materialproperty-create-modal'),
    path('properties/<int:pk>/', views.MaterialPropertyDetailView.as_view(), name='materialproperty-detail'),
    path('properties/<int:pk>/modal/', views.MaterialPropertyModalDetailView.as_view(), name='materialproperty-detail-modal'),
    path('properties/<int:pk>/update/', views.MaterialPropertyUpdateView.as_view(), name='materialproperty-update'),
    path('properties/<int:pk>/update/modal/', views.MaterialPropertyModalUpdateView.as_view(), name='materialproperty-update-modal'),
    path('properties/<int:pk>/delete/modal/', views.MaterialPropertyModalDeleteView.as_view(), name='materialproperty-delete-modal'),
    path('property_values/<int:pk>/delete/modal/', views.MaterialPropertyValueModalDeleteView.as_view(), name='materialpropertyvalue-delete-modal'),
    path('compositions/', views.CompositionListView.as_view(), name='composition-list'),
    path('compositions/create/', views.CompositionCreateView.as_view(), name='composition-create'),
    path('compositions/create/modal/', views.CompositionCreateView.as_view(), name='composition-create-modal'),
    path('compositions/<int:pk>/', views.CompositionDetailView.as_view(), name='composition-detail'),
    path('compositions/<int:pk>/modal/', views.CompositionModalDetailView.as_view(), name='composition-detail-modal'),
    path('compositions/<int:pk>/update/', views.CompositionUpdateView.as_view(), name='composition-update'),
    path('compositions/<int:pk>/update/modal', views.CompositionModalUpdateView.as_view(), name='composition-update-modal'),
    path('compositions/<int:pk>/delete/', views.CompositionModalDeleteView.as_view(), name='composition-delete-modal'),
    path('compositions/<int:pk>/add_component/', views.AddComponentView.as_view(), name='composition-add-component'),
    path('compositions/<int:pk>/order_up/', views.CompositionOrderUpView.as_view(), name='composition-order-up'),
    path('compositions/<int:pk>/order_down/', views.CompositionOrderDownView.as_view(), name='composition-order-down'),
    path('materialcomponentgroups/settings/<int:pk>/add_source/', views.AddSourceView.as_view(), name='add_source'),
    path('materialcomponentgroups/settings/<int:pk>/remove_seasonal_variation/<int:distribution_pk>/', views.RemoveSeasonalVariationView.as_view(), name='remove_seasonal_variation'),
    path('weightshares/<int:pk>/delete/', views.WeightShareModalDeleteView.as_view(), name='weightshare-delete-modal'),
    path('api/', include(router.urls)),
]
