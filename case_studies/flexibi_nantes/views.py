from django.db.models import Sum
from django.http import JsonResponse
from django.views.generic import FormView
from rest_framework.views import APIView

from .forms import NantesGreenhousesFilterForm
from .models import NantesGreenhouses
from .serializers import NantesGreenhousesGeometrySerializer


class NantesGreenhousesView(FormView):
    template_name = 'explore_nantes_greenhouses.html'
    form_class = NantesGreenhousesFilterForm
    initial = {'heated': 'Yes', 'lighted': 'Yes'}


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
            crops.append('Cucumber')
        if request.GET.get('tomato') == 'true':
            crops.append('Tomato')

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
