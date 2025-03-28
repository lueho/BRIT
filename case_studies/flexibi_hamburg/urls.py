from django.urls import include, path
from django.views.generic import RedirectView

from .router import router
from .views import (HamburgRoadsideTreeCatchmentAutocompleteView, HamburgRoadsideTreesListFileExportView,
                    RoadsideTreesMapIframeView, RoadsideTreesMapView)

urlpatterns = [
    path('roadside_trees/map/', RoadsideTreesMapView.as_view(), name='HamburgRoadsideTrees'),
    path('roadside_trees/map/iframe/', RoadsideTreesMapIframeView.as_view(), name='HamburgRoadsideTreesIframe'),
    path('roadside_trees/export/', HamburgRoadsideTreesListFileExportView.as_view(),
         name='hamburgroadsidetrees-export'),
    path('roadside_trees/catchment_autocomplete/', HamburgRoadsideTreeCatchmentAutocompleteView.as_view(),
         name='hamburgroadsidetrees-catchment-autocomplete'),
    path('green_areas/map/', RedirectView.as_view(url='/maps/', permanent=True), name='HamburgGreenAreas'),
    path('api/', include(router.urls)),
]
