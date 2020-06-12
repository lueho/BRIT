from django.urls import path

from .views import ScenarioResultView, ScenarioResultDetailMapView

urlpatterns = [
    path('scenarios/<int:pk>', ScenarioResultView.as_view(), name='scenario_result'),
    path('scenarios/<int:pk>/<int:algo_pk>/', ScenarioResultDetailMapView.as_view(), name='scenario_result_map'),
]
