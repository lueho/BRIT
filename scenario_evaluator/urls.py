from django.urls import path

from .views import ScenarioListView, ScenarioResultView, ScenarioResultDetailMapView

urlpatterns = [
    path('scenarios/', ScenarioListView.as_view(), name='scenario_result_list'),
    path('scenarios/<int:pk>/', ScenarioResultView.as_view(), name='scenario_result'),
    path('scenarios/<int:pk>/<int:algorithm_pk>/', ScenarioResultDetailMapView.as_view(), name='scenario_result_map'),
]
