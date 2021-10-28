from django.urls import path

from inventories.views import get_evaluation_status
from .views import (ScenarioEvaluationProgressView,
                    ScenarioListView,
                    ScenarioResultView,
                    ScenarioResultDetailMapView,
                    download_scenario_result_summary
                    )

urlpatterns = [
    path('scenarios/', ScenarioListView.as_view(), name='scenario_result_list'),
    path('scenarios/<int:pk>/', ScenarioResultView.as_view(), name='scenario_result'),
    path('scenarios/<int:pk>/<int:algorithm_pk>/<int:feedstock_pk>', ScenarioResultDetailMapView.as_view(),
         name='scenario_result_map'),
    path('scenarios/<int:pk>/evaluating/', ScenarioEvaluationProgressView.as_view(),
         name='scenario_evaluation_progress'),
    path('scenarios/evaluating/<str:task_id>/', get_evaluation_status, name='get_evaluation_status'),
    path('scenarios/<int:scenario_pk>/download_result_summary/', download_scenario_result_summary, name='download_result_summary')
]
