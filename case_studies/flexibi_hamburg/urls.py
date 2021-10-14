from django.urls import path

from .views import HamburgRoadsideTreeAPIView, TreeFilterView

urlpatterns = [
    path('roadside_trees/data/', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('roadside_trees/', TreeFilterView.as_view(), name='HamburgRoadsideTrees'),
]
