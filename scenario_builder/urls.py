from django.urls import path
from .views import (CatchmentDefinitionView,
                    catchmentView,
                    CatchmentAPIView,
                    FeedstockDefinitionView)


urlpatterns = [
    path('scenario_builder/', FeedstockDefinitionView.as_view(), name='feedstock_definition'),
    path('catchment_definition/', CatchmentDefinitionView.as_view(), name='catchment_definition'),
    path('catchment_view/', catchmentView, name='catchment_view'),
    path('data.catchment_geometries/', CatchmentAPIView.as_view(), name='data.catchment_geometries'),
]