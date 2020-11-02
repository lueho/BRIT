from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.views.generic import ListView, FormView
from rest_framework.views import APIView

from gis_source_manager.models import HamburgRoadsideTrees, NantesGreenhouses
from .forms import HamburgRoadsideTreeFilterForm, NantesGreenhousesFilterForm
from scenario_builder.models import GeoDataset
from .serializers import HamburgRoadsideTreeGeometrySerializer, NantesGreenhousesGeometrySerializer


class BioresourceExplorerHomeView(ListView):
    queryset = GeoDataset.objects.all()
    template_name = 'bioresource_explorer_home.html'


class HamburgExplorerView(LoginRequiredMixin, FormView):
    template_name = 'explore_hamburg_roadsidetrees.html'
    form_class = HamburgRoadsideTreeFilterForm

    def get_form_kwargs(self):
        form_kwargs = super(HamburgExplorerView, self).get_form_kwargs()
        return form_kwargs


class NantesGreenhousesView(FormView):
    template_name = 'explore_nantes_greenhouses.html'
    form_class = NantesGreenhousesFilterForm
    initial = {'heated': 'Yes', 'lighted': 'Yes'}


def is_valid_queryparam(param):
    return param != '' and param is not None


class HamburgRoadsideTreeAPIView(APIView):

    @staticmethod
    def get(request):
        qs = HamburgRoadsideTrees.objects.all()
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

        serializer = HamburgRoadsideTreeGeometrySerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'tree_count': len(serializer.data['features'])
            }
        }

        return JsonResponse(data, safe=False)


class NantesGreenhousesAPIView(APIView):

    @staticmethod
    def get(request):
        qs = NantesGreenhouses.objects.all()

        if request.GET.get('lighting') == '2':
            qs = qs.filter(lighted=True)
        elif request.GET.get('lighting') == '3':
            qs = qs.filter(lighted=False)

        if request.GET.get('heating') == '2':
            qs = qs.filter(heated=True)
        elif request.GET.get('heating') == '3':
            qs = qs.filter(heated=False)

        if request.GET.get('prod_mode') == '2':
            qs = qs.filter(above_ground=False)
        elif request.GET.get('prod_mode') == '3':
            qs = qs.filter(above_ground=True)

        if request.GET.get('cult_man') == '2':
            qs = qs.filter(high_wire=False)
        elif request.GET.get('cult_man') == '3':
            qs = qs.filter(heated=True)

        crops = []
        if request.GET.get('cucumber') == 'true':
            crops.append('Concombre')
        if request.GET.get('tomato') == 'true':
            crops.append('Tomate')

        qs = qs.filter(culture_1__in=crops)

        serializer = NantesGreenhousesGeometrySerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'gh_count': len(serializer.data['features']),
                'gh_surface': round(qs.aggregate(Sum('surface_ha'))['surface_ha__sum'], 1)
            }
        }

        return JsonResponse(data, safe=False)
