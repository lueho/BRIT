from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.filters import InBBoxFilter
from .models import HH_Roadside
from flexibi_dst.models import Districts_HH
from .serializers import TreeSerializer
from .filters import TreeFilter, TreeFilterSet
from django.shortcuts import render
from django_filters import rest_framework as filters
from django.http import QueryDict

class TreeViewSet(ReadOnlyModelViewSet):
    queryset = HH_Roadside.objects.all()
    serializer_class = TreeSerializer
    filter_backends = (filters.DjangoFilterBackend)
    # filterset_fields = ('gattung_deutsch', 'bezirk', 'pflanzjahr', 'stammumfang',)
    filterset_class = TreeFilterSet
    # bbox_filter_field = 'geom'
    # filter_backends = (InBBoxFilter, )
    # queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Buche', pflanzjahr__gt=1980, geom__intersects=Districts_HH.objects.get(name='Bergedorf').geom)
    
def treeSearch(request):
    queryset = HH_Roadside.objects.all()
    tree_filter = TreeFilter(request.GET, queryset=queryset)
    return render(request, 'tree_list.html', {'filter': tree_filter})
    
def is_valid_queryparam(param):
    return param != '' and param is not None


def BootstrapTreeView(request):
    qs = HH_Roadside.objects.all()
    districts = Districts_HH.objects.all()
    gattung_deutsch_query = request.GET.get('gattung_deutsch')
    pflanzjahr_min_query = request.GET.get('pflanzjahr_min')
    pflanzjahr_max_query = request.GET.get('pflanzjahr_max')
    district_query = request.GET.get('district')

    if is_valid_queryparam(gattung_deutsch_query):
        qs = qs.filter(gattung_deutsch__icontains=gattung_deutsch_query)

    if is_valid_queryparam(pflanzjahr_min_query):
        qs = qs.filter(pflanzjahr__gte=pflanzjahr_min_query)

    if is_valid_queryparam(pflanzjahr_max_query):
        qs = qs.filter(pflanzjahr__lt=pflanzjahr_max_query)
        
    if is_valid_queryparam(district_query) and district_query != 'Bitte wählen...':
        qs = qs.filter(bezirk__icontains=district_query)

    context = {
        'queryset': qs,
        'districts': districts
    }
    return render(request, "bootstrap_form.html", context)