from django.urls import path
from django.views.generic import ListView, TemplateView
from djgeojson.views import GeoJSONLayerView
from .models import HH_Roadside

class TreeList(ListView):
    queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Erle', bezirk='Altona')
    
# class TreeGeoJson(ListView):
    # queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Erle', bezirk='Altona')
    
urlpatterns = [
    # path('', TreeList.as_view(template_name = 'tree_map.html')),
    path('', TemplateView.as_view(template_name = 'tree_map_json.html'), name='home_map'),
    path('data.geojson', GeoJSONLayerView.as_view(model=HH_Roadside, properties=('gattung_deutsch', 'stammumfang', 'bezirk')), name='tree_data'),
]