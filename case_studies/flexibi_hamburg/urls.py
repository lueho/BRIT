from django.urls import path

from .views import HamburgRoadsideTreeAPIView, RoadsideTreesMapView

urlpatterns = [
    path('roadside_trees/data/', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('<int:pk>/', RoadsideTreesMapView.as_view(), name='HamburgRoadsideTrees'),
]
