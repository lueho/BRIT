from django.urls import path

from .views import (CatchmentDefinitionView,
                    catchmentView,
                    CatchmentAPIView,
                    FeedstockDefinitionView,
                    ScenarioListView,
                    ScenarioDetailView,
                    ScenarioResultView)

urlpatterns = [
    path('scenario_builder/', FeedstockDefinitionView.as_view(), name='feedstock_definition'),
    path('catchment_definition/', CatchmentDefinitionView.as_view(), name='catchment_definition'),
    path('catchment_view/', catchmentView, name='catchment_view'),
    path('data.catchment_geometries/', CatchmentAPIView.as_view(), name='data.catchment_geometries'),
    path('scenarios/', ScenarioListView.as_view(), name='scenarios'),
    path('scenarios/<int:pk>/', ScenarioDetailView.as_view(), name='scenario_detail'),
    path('scenarios/<int:pk>/result/', ScenarioResultView.as_view(), name='scenario_result'),
]
