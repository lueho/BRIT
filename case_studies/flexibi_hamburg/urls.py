from django.urls import include, path

from .router import router
from .views import (HamburgRoadsideTreeAPIView, RoadsideTreesMapView, HamburgRoadsideTreesListFileExportView,
                    HamburgRoadsideTreesListFileExportProgressView)

urlpatterns = [
    path('roadside_trees/data/', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('roadside_trees/map/', RoadsideTreesMapView.as_view(), name='HamburgRoadsideTrees'),
    path('roadside_trees/export/', HamburgRoadsideTreesListFileExportView.as_view(), name='hamburgroadsidetrees-export'),
    path('roadside_trees/export/<str:task_id>/progress/', HamburgRoadsideTreesListFileExportProgressView.as_view(), name='hamburgroadsidetrees-export-progress'),
    path('api/', include(router.urls)),
]
