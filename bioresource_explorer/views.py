from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import TemplateView
from rest_framework.views import APIView
from flexibi_dst.models import Districts_HH
from .models import HH_Roadside
from .serializers import TreeSerializer

class BioresourceExplorerHomeView(TemplateView):
    template_name = 'bioresource_explorer_home.html'
    
class HamburgExplorerView(TemplateView):
    template_name = 'tree_map_json.html'
    
class NantesExplorerView(TemplateView):
    template_name = 'tree_map_json.html'
    
def is_valid_queryparam(param):
    return param != '' and param is not None

class HamburgRoadsideTreeAPIView(APIView):

    def get(self, request):
        qs = HH_Roadside.objects.all()
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
