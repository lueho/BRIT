from django.urls import path

from .views import (BioresourceExplorerHomeView,
                    HamburgExplorerView,
                    HamburgRoadsideTreeAPIView,
                    NantesGreenhousesView,
                    NantesGreenhousesAPIView,
                    )

urlpatterns = [
    path('', BioresourceExplorerHomeView.as_view(), name='bioresource_explorer_home'),
    path('data.hamburg_roadside_trees/', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('data.nantes_greenhouses/', NantesGreenhousesAPIView.as_view(), name='data.nantes_greenhouses'),
    path('hamburg/', HamburgExplorerView.as_view(), name='hamburg_explorer'),
    path('nantes/', NantesGreenhousesView.as_view(), name='nantes_greenhouses'),
]
