from django.urls import path
from .views import (CatchmentDefinitionView,
                    FeedstockDefinitionView)

urlpatterns = [
    path('scenario_builder/', FeedstockDefinitionView.as_view(), name='feedstock_definition'),
    path('catchment_definition/', CatchmentDefinitionView.as_view(), name='catchment_definition'),
]