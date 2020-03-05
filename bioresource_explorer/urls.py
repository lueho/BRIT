from django.urls import path
from django.views.generic import ListView, TemplateView
from djgeojson.views import GeoJSONLayerView
from .models import HH_Roadside
from .views import GeoJSONTreeData, TreeMapView, BioresourceExplorerHomeView, TreeAnalysisResults

urlpatterns = [
    path('', BioresourceExplorerHomeView.as_view(), name='bioresource_explorer_home'),
    path('data.hamburg_roadside_trees/', GeoJSONTreeData, name='data.hamburg_roadside_trees'),
    path('hamburg/', TreeMapView.as_view(), name='hamburg_explorer'),
    path('nantes/', TreeMapView.as_view(), name='nantes_explorer'),
    path ('roadside_trees/', TreeMapView, name='roadside_trees'),
    path('data.tree_analysis/', TreeAnalysisResults, name='tree_analysis_results'),
]