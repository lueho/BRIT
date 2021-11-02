from django.urls import include, path

from .views import (
    get_evaluation_status,
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
    load_catchment_options,
    load_geodataset_options,
    load_algorithm_options,
    load_parameter_options,
    ScenarioEvaluationProgressView,
    ScenarioResultView,
    ScenarioResultDetailMapView,
    download_scenario_result_summary
)

urlpatterns = [

    path('materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/',
         SeasonalDistributionCreateView.as_view(),
         name='seasonal_distribution_create'),
    path('scenarios/', ScenarioListView.as_view(), name='scenario_list'),
    path('scenarios/create/', ScenarioCreateView.as_view(), name='scenario_create'),
    path('scenarios/<int:pk>/', ScenarioDetailView.as_view(), name='scenario_detail'),
    path('scenarios/<int:pk>/result/', ScenarioResultView.as_view(), name='scenario_result'),
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
    path('scenarios/<int:pk>/<int:algorithm_pk>/<int:feedstock_pk>', ScenarioResultDetailMapView.as_view(),
         name='scenario_result_map'),
    path('scenarios/<int:pk>/evaluating/', ScenarioEvaluationProgressView.as_view(),
         name='scenario_evaluation_progress'),
    path('scenarios/evaluating/<str:task_id>/', get_evaluation_status, name='get_evaluation_status'),
    path('scenarios/<int:scenario_pk>/download_result_summary/', download_scenario_result_summary,
         name='download_result_summary'),
    path('scenarios/<int:scenario_pk>/report/', download_scenario_summary, name='download_scenario_summary'),
    path('ajax/catchment-options/', load_catchment_options, name='ajax_catchment_options'),
    path('ajax/load-geodatasets/', load_geodataset_options, name='ajax_load_geodatasets'),
    path('ajax/load-algorithms/', load_algorithm_options, name='ajax_load_inventory_algorithms'),
    path('ajax/load-inventory-parameters/', load_parameter_options, name='ajax_load_inventory_parameters'),
    path('ajax/result_layer/<layer_name>/', ResultMapAPI.as_view(), name='data.result_layer'),
]
