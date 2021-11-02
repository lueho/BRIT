from django.http import JsonResponse
from django.views.generic import TemplateView
from django.shortcuts import reverse
from rest_framework.views import APIView

from inventories.models import GeoDataset
from .filters import TreeFilter
from .models import HamburgRoadsideTrees
from .serializers import HamburgRoadsideTreeGeometrySerializer


class TreeFilterView(TemplateView):
    template_name = 'maps_base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        geodataset = GeoDataset.objects.get(model_name='HamburgRoadsideTrees')
        form_fields = {key: type(value.field).__name__ for key, value in TreeFilter.base_filters.items()}
        context.update({
            'map_header': 'Hamburg Roadside Trees',
            'form': TreeFilter(self.request.GET).form,
            'geodataset': geodataset,
            'map_config': {
                'form_fields': form_fields,
                'region_url': reverse('ajax_region_geometries'),
                'feature_url': reverse('data.hamburg_roadside_trees'),
                'region_id': 3,
                'load_features': False,
                'markerStyle': {
                    'color': '#63c36c',
                    'fillOpacity': 1,
                    'radius': 5,
                    'stroke': False
                }
            }
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
