from django.urls import include, path

from .views import (CatchmentCreateView,
                    CatchmentBrowseView,
                    CatchmentGeometryAPI,
                    CatchmentUpdateView,
                    CatchmentDeleteView,
                    MaterialListView,
                    MaterialCreateView,
                    MaterialDetailView,
                    MaterialUpdateView,
                    MaterialDeleteView,
                    MaterialComponentCreateView,
                    MaterialComponentUpdateView,
                    MaterialComponentDeleteView,
                    MaterialComponentGroupListView,
                    MaterialComponentGroupCreateView,
                    MaterialComponentGroupDetailView,
                    MaterialComponentGroupUpdateView,
                    MaterialComponentGroupDeleteView,
                    MaterialComponentGroupCompositionView,
                    MaterialComponentShareUpdateView,
                    MaterialComponentGroupAddComponentView,
                    MaterialComponentGroupRemoveComponentView,
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
    path('materialcomponents/', MaterialComponentGroupListView.as_view(), name='material_component_list'),
    path('materialcomponentgroups/', MaterialComponentGroupListView.as_view(), name='material_component_group_list'),
    path('materialcomponentgroups/create/', MaterialComponentGroupCreateView.as_view(),
         name='material_component_group_create'),
    path('materialcomponentgroups/<int:pk>/', MaterialComponentGroupDetailView.as_view(),
         name='material_component_group_detail'),
    path('materialcomponentgroups/<int:pk>/update/', MaterialComponentGroupUpdateView.as_view(),
         name='material_component_group_update'),
    path('materialcomponentgroups/<int:pk>/delete/', MaterialComponentGroupDeleteView.as_view(),
         name='material_component_group_delete'),
    path('materialcomponentgroupshares/<int:pk>/update/', MaterialComponentShareUpdateView.as_view(),
         name='material_component_group_share_update'),
    path('materialcomponentgroupshare/<int:pk>/remove/', MaterialComponentGroupRemoveComponentView.as_view(),
         name='material_component_group_share_remove_component'),
    path('scenarios/', ScenarioListView.as_view(), name='scenario_list'),
    path('scenarios/create/', ScenarioCreateView.as_view(), name='create_scenario'),
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
    path('scenarios/<int:scenario_pk>/materials/', MaterialListView.as_view(), name='material_list'),
    path('scenarios/<int:scenario_pk>/materials/create/', MaterialCreateView.as_view(), name='material_create'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/', MaterialDetailView.as_view(),
         name='material_detail'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/update/', MaterialUpdateView.as_view(),
         name='material_update'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/delete/', MaterialDeleteView.as_view(),
         name='material_delete'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/add_component/',
         MaterialComponentCreateView.as_view(),
         name='material_component_create'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/update_component/<int:component_pk>/',
         MaterialComponentUpdateView.as_view(), name='material_component_update'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/delete_component/<int:component_pk>/',
         MaterialComponentDeleteView.as_view(),
         name='material_component_delete'),
    path(
        'scenarios/<int:scenario_pk>/materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/',
        SeasonalDistributionCreateView.as_view(),
        name='seasonal_distribution_create'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/component_groups/<int:group_pk>/composition/',
         MaterialComponentGroupCompositionView.as_view(), name='material_component_group_composition'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/component_groups/<int:group_pk>/add_component/',
         MaterialComponentGroupAddComponentView.as_view(), name='material_component_group_add_component'),
    path('ajax/catchment-options/', load_catchment_options, name='ajax_catchment_options'),
    path('ajax/catchment_geometries/', CatchmentGeometryAPI.as_view(), name='ajax_catchment_geometries'),
    path('ajax/region_geometries/', RegionGeometryAPI.as_view(), name='ajax_region_geometries'),
    path('ajax/load-geodatasets/', load_geodataset_options, name='ajax_load_geodatasets'),
    path('ajax/load-algorithms/', load_algorithm_options, name='ajax_load_inventory_algorithms'),
    path('ajax/load-inventory-parameters/', load_parameter_options, name='ajax_load_inventory_parameters'),
    path('ajax/result_layer/<layer_name>/', ResultMapAPI.as_view(), name='data.result_layer'),
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
]
