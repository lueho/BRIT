from django.http import JsonResponse
from django.views.generic import TemplateView
from rest_framework.views import APIView

from .models import HamburgRoadsideTrees
from .serializers import HamburgRoadsideTreeGeometrySerializer
from .filters import TreeFilter


class TreeFilterView(TemplateView):
    template_name = 'map_hamburg_roadsidetrees.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'map_header': 'Hamburg Roadside Trees',
            'tree_filter': TreeFilter(self.request.GET),
        })
        return context


def is_valid_queryparam(param):
    return param != '' and param is not None


class HamburgRoadsideTreeAPIView(APIView):

    @staticmethod
    def get(request):
        qs = HamburgRoadsideTrees.objects.all()

        # Tree genus filter
        exclude = ['Linde', 'Eiche', 'Ahorn']
        gattung_deutsch_query = request.query_params.getlist('gattung_deutsch[]')
        if is_valid_queryparam(gattung_deutsch_query):
            if 'Other' in gattung_deutsch_query:
                gattung_deutsch_query.remove('Other')
                for tree_type in gattung_deutsch_query:
                    exclude.remove(tree_type)
                qs = qs.exclude(gattung_deutsch__in=exclude)
            else:
                qs = qs.filter(gattung_deutsch__in=gattung_deutsch_query)

        # City district filter
        district_query = request.query_params.getlist('bezirk[]')
        if is_valid_queryparam(district_query):
            qs = qs.filter(bezirk__in=district_query)

        # Year of plantation filter
        pflanzjahr_min_query = request.GET.get('pflanzjahr_min')
        pflanzjahr_max_query = request.GET.get('pflanzjahr_max')

        if is_valid_queryparam(pflanzjahr_min_query):
            qs = qs.filter(pflanzjahr__gte=pflanzjahr_min_query)

        if is_valid_queryparam(pflanzjahr_max_query):
            qs = qs.filter(pflanzjahr__lte=pflanzjahr_max_query)

        serializer = HamburgRoadsideTreeGeometrySerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'tree_count': {
                    'label': 'Number of trees',
                    'value': len(serializer.data['features'])
                },
            }
        }

        return JsonResponse(data, safe=False)
