from django.urls import path
from .views import (BioresourceExplorerHomeView,
                    HamburgExplorerView,
                    HamburgExplorerViewTest,
                    HamburgRoadsideTreeAPIView,
                    NantesExplorerView)

urlpatterns = [
    path('', BioresourceExplorerHomeView.as_view(), name='bioresource_explorer_home'),
    path('data.hamburg_roadside_trees/', HamburgRoadsideTreeAPIView.as_view(), name='data.hamburg_roadside_trees'),
    path('hamburg/', HamburgExplorerView.as_view(), name='hamburg_explorer'),
    path('nantes/', NantesExplorerView.as_view(), name='nantes_explorer'),
    path('hamburg_test/', HamburgExplorerViewTest.as_view(), name='hamburg_explorer_test'),
]