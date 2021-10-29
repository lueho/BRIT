from django.urls import include, path

from .views import (CatchmentCreateView,
                    CatchmentBrowseView,
                    CatchmentGeometryAPI,
                    CatchmentUpdateView,
                    CatchmentDeleteView,
                    RegionGeometryAPI,
                    ScenarioDetailView,
                    ScenarioListView,
                    ScenarioCreateView,
                    ScenarioDeleteView,
                    ScenarioUpdateView,
                    SeasonalDistributionCreateView,
                    ResultMapAPI,
                    ScenarioAddInventoryAlgorithmView,
                    ScenarioRemoveInventoryAlgorithmView,
                    ScenarioAlgorithmConfigurationUpdateView,
                    download_scenario_summary,
                    load_geodataset_options,
                    load_algorithm_options,
                    load_parameter_options,
                    load_catchment_options,
                    )

urlpatterns = [
    path('catchments/', CatchmentBrowseView.as_view(), name='catchment_list'),
    path('catchment/create/', CatchmentCreateView.as_view(), name='catchment_definition'),
    path('catchments/<int:pk>/update/', CatchmentUpdateView.as_view(), name='catchment_update'),
    path('catchments/<int:pk>/delete/', CatchmentDeleteView.as_view(), name='catchment_delete'),
    path('materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/',
         SeasonalDistributionCreateView.as_view(),
         name='seasonal_distribution_create'),
    path('scenarios/', ScenarioListView.as_view(), name='scenario_list'),
    path('scenarios/create/', ScenarioCreateView.as_view(), name='scenario_create'),
    path('scenarios/<int:pk>/', ScenarioDetailView.as_view(), name='scenario_detail'),
    path('scenarios/<int:pk>/update/', ScenarioUpdateView.as_view(), name='scenario_update'),
    path('scenarios/<int:pk>/delete/', ScenarioDeleteView.as_view(), name='scenario_delete'),
    path('scenarios/<int:pk>/add_inventory_algorithm/', ScenarioAddInventoryAlgorithmView.as_view(),
         name='add_scenario_configuration'),
    path('scenarios/<int:scenario_pk>/change_config/<int:algorithm_pk>/',
         ScenarioAlgorithmConfigurationUpdateView.as_view(),
         name='scenario_update_config'),
    path('scenarios/<int:scenario_pk>/configuration/<int:feedstock_pk>/<int:algorithm_pk>/remove/',
         ScenarioRemoveInventoryAlgorithmView.as_view(),
         name='remove_algorithm_from_scenario'),
    path(
        'scenarios/<int:scenario_pk>/materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/',
        SeasonalDistributionCreateView.as_view(),
        name='seasonal_distribution_create'),
    path('scenarios/<int:scenario_pk>/report/', download_scenario_summary, name='download_scenario_summary'),
    path('ajax/catchment-options/', load_catchment_options, name='ajax_catchment_options'),
    path('ajax/catchment_geometries/', CatchmentGeometryAPI.as_view(), name='ajax_catchment_geometries'),
    path('ajax/region_geometries/', RegionGeometryAPI.as_view(), name='ajax_region_geometries'),
    path('ajax/load-geodatasets/', load_geodataset_options, name='ajax_load_geodatasets'),
    path('ajax/load-algorithms/', load_algorithm_options, name='ajax_load_inventory_algorithms'),
    path('ajax/load-inventory-parameters/', load_parameter_options, name='ajax_load_inventory_parameters'),
    path('ajax/result_layer/<layer_name>/', ResultMapAPI.as_view(), name='data.result_layer'),
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
]