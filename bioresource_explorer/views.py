from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.filters import InBBoxFilter
from rest_framework.serializers import Serializer
from rest_framework import serializers
from .models import HH_Roadside
from flexibi_dst.models import Districts_HH
from .serializers import TreeSerializer
from .filters import TreeFilter, TreeFilterSet
from django.shortcuts import render
from django_filters import rest_framework as filters
from django.http import QueryDict, JsonResponse
from urllib.parse import urlencode
from django.views.generic import TemplateView

class BioresourceExplorerHomeView(TemplateView):
    template_name = 'bioresource_explorer_home.html'
    
class TreeMapView(TemplateView):
    template_name = 'tree_map_json.html'
    
def is_valid_queryparam(param):
    return param != '' and param is not None

def GeoJSONTreeData(request):
    qs = HH_Roadside.objects.all()
    districts = Districts_HH.objects.all()
    gattung_deutsch_query = request.GET.get('gattung_deutsch')
    pflanzjahr_min_query = request.GET.get('pflanzjahr_min')
    pflanzjahr_max_query = request.GET.get('pflanzjahr_max')
    district_query = request.GET.get('bezirk')

    if is_valid_queryparam(gattung_deutsch_query):
        qs = qs.filter(gattung_deutsch__icontains=gattung_deutsch_query)

    if is_valid_queryparam(pflanzjahr_min_query):
        qs = qs.filter(pflanzjahr__gte=pflanzjahr_min_query)

    if is_valid_queryparam(pflanzjahr_max_query):
        qs = qs.filter(pflanzjahr__lt=pflanzjahr_max_query)
        
    if is_valid_queryparam(district_query) and district_query != 'Bitte wählen...':
        qs = qs.filter(bezirk__icontains=district_query)
        
        
    serializer = TreeSerializer(qs, many=True)
    data = {
        'geoJson': serializer.data,
        'analysis': {
            'tree_count': len(serializer.data['features'])
        }
    }

    return JsonResponse(data, safe=False)
    
def TreeAnalysisResults(request):
    qs = HH_Roadside.objects.all()
    districts = Districts_HH.objects.all()
    gattung_deutsch_query = request.GET.get('gattung_deutsch')
    pflanzjahr_min_query = request.GET.get('pflanzjahr_min')
    pflanzjahr_max_query = request.GET.get('pflanzjahr_max')
    district_query = request.GET.get('bezirk')

    if is_valid_queryparam(gattung_deutsch_query):
        qs = qs.filter(gattung_deutsch__icontains=gattung_deutsch_query)

    if is_valid_queryparam(pflanzjahr_min_query):
        qs = qs.filter(pflanzjahr__gte=pflanzjahr_min_query)

    if is_valid_queryparam(pflanzjahr_max_query):
        qs = qs.filter(pflanzjahr__lt=pflanzjahr_max_query)
        
    if is_valid_queryparam(district_query) and district_query != 'Bitte wählen...':
        qs = qs.filter(bezirk__icontains=district_query)
        
    serializer = TreeSerializer(qs, many=True)
    data = serializer.data
    
    response = {
        'tree_count': len(data['features'])
    }
    
    return JsonResponse(response, safe=False)
    
