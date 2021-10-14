from django.urls import path

from .views import (
    HamburgExplorerView,
    HamburgRoadsideTreeAPIView,
)

urlpatterns = [
    path('roadside_trees/data', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('green_spaces/', HamburgExplorerView.as_view(), name='HamburgGreenAreas'),
    path('roadside_trees/', HamburgExplorerView.as_view(), name='HamburgRoadsideTrees'),
]
