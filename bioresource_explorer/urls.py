from django.urls import path
from django.views.generic import ListView, TemplateView
from djgeojson.views import GeoJSONLayerView
from .models import HH_Roadside
from .views import GeoJSONTreeData, TreeMapView, BioresourceExplorerHomeView, TreeAnalysisResults

urlpatterns = [
    path('', BioresourceExplorerHomeView, name='bioresource_explorer_home'),
    path('data.hamburg_roadside_trees/', GeoJSONTreeData, name='data.hamburg_roadside_trees'),
    path('hamburg/', TreeMapView, name='hamburg_explorer'),
    path('nantes/', TreeMapView, name='hamburg_explorer'),
    path ('roadside_trees/', TreeMapView, name='roadside_trees'),
    path('data.tree_analysis/', TreeAnalysisResults, name='tree_analysis_results'),
]