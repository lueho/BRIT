from django.urls import path

from .views import (AlgorithmNameAutocompleteView, ResultMapAPI, ScenarioCreateView, ScenarioDetailView,
                    ScenarioEvaluationProgressView,
                    ScenarioModalDeleteView, ScenarioResultDetailMapView,
                    ScenarioResultView, ScenarioUpdateView, SeasonalDistributionCreateView, UserOwnedScenarioFilterView,
                    download_scenario_result_summary, download_scenario_summary, get_evaluation_status,
                    ParameterValueNameAutocompleteView,
                    PublishedScenarioFilterView, ScenarioNameAutocompleteView, ScenarioConfigurationCreateView,
                    ScenarioInventoryConfigurationModalDeleteView, ScenarioConfigurationUpdateView)

urlpatterns = [
    path('materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/',
         SeasonalDistributionCreateView.as_view(),
         name='seasonal_distribution_create'),
    path('scenarios/', PublishedScenarioFilterView.as_view(), name='scenario-list'),
    path('scenarios/user/', UserOwnedScenarioFilterView.as_view(), name='scenario-list-owned'),
    path('scenarios/autocomplete/name/', ScenarioNameAutocompleteView.as_view(), name='scenario-name-autocomplete'),
    path('scenarios/create/', ScenarioCreateView.as_view(), name='scenario-create'),
    path('scenarios/<int:pk>/', ScenarioDetailView.as_view(), name='scenario-detail'),
    path('scenarios/<int:pk>/update/', ScenarioUpdateView.as_view(), name='scenario-update'),
    path('scenarios/<int:pk>/delete/', ScenarioModalDeleteView.as_view(), name='scenario-delete-modal'),
    path('scenarios/<int:pk>/result/', ScenarioResultView.as_view(), name='scenario-result'),
    path('scenario_configurations/<int:pk>/update/', ScenarioConfigurationUpdateView.as_view(), name='scenarioinventory-update'),
    path('scenario_configurations/<int:pk>/delete/', ScenarioInventoryConfigurationModalDeleteView.as_view(), name='scenarioinventory-delete-modal'),
    path('scenarios/<int:scenario_pk>/inventories/create/', ScenarioConfigurationCreateView.as_view(), name='scenarioinventory-create'),
    path('scenarios/<int:scenario_pk>/materials/<int:material_pk>/<int:component_pk>/seasonal_distributions/create/', SeasonalDistributionCreateView.as_view(), name='seasonal_distribution_create'),
    path('scenarios/<int:pk>/<int:algorithm_pk>/<int:feedstock_pk>', ScenarioResultDetailMapView.as_view(), name='scenario_result_map'),
    path('scenarios/<int:pk>/evaluating/', ScenarioEvaluationProgressView.as_view(), name='scenario_evaluation_progress'),
    path('scenarios/evaluating/<str:task_id>/', get_evaluation_status, name='get_evaluation_status'),
    path('scenarios/<int:scenario_pk>/download_result_summary/', download_scenario_result_summary, name='download_result_summary'),
    path('scenarios/<int:scenario_pk>/report/', download_scenario_summary, name='download_scenario_summary'),
    path('parametervalues/autocomplete/name/', ParameterValueNameAutocompleteView.as_view(), name='parametervalue-name-autocomplete'),
    path('algorithms/autocomplete/name/', AlgorithmNameAutocompleteView.as_view(), name='algorithm-name-autocomplete'),
    path('ajax/result_layer/<layer_name>/', ResultMapAPI.as_view(), name='data.result_layer'),
]
