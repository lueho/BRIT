from django.urls import path
from django.views.generic import ListView, TemplateView
from djgeojson.views import GeoJSONLayerView
from .models import HH_Roadside
from rest_framework.routers import DefaultRouter
from .views import TreeViewSet, BootstrapTreeView, GeoJSONTreeData, TreeMapView, BioresourceExplorerHomeView
from .views import treeSearch

# router = DefaultRouter()
# router.register(r'markers', TreeViewSet)

tree_json = TreeViewSet.as_view({
    'get': 'list'
})

# urlpatterns = router.urls

# class TreeList(ListView):
    # queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Erle', bezirk='Altona')
    
# class TreeGeoJson(ListView):
    # queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Erle', bezirk='Altona')
    
urlpatterns = [
    # path('', TreeList.as_view(template_name = 'tree_map.html')),
    # path('', TemplateView.as_view(template_name = 'tree_map_json.html'), name='home_map'),
    path('', BioresourceExplorerHomeView, name='bioresource_explorer_home'),
    # path('data.geojson', GeoJSONLayerView.as_view(model=HH_Roadside, properties=('gattung_deutsch', 'stammumfang', 'bezirk')), name='tree_data'),
    path('data.geojson', tree_json, name='tree_data'),
    path('treesearch/', treeSearch, name='tree_search'),
    path('bootstrap/', BootstrapTreeView, name='bootstrap'),
    path('data.hamburg_roadside_trees/', GeoJSONTreeData, name='data.hamburg_roadside_trees'),
    path('hamburg/', TreeMapView, name='hamburg_explorer'),
    path('nantes/', TreeMapView, name='hamburg_explorer'),
    path ('roadside_trees/', TreeMapView, name='roadside_trees'),
]