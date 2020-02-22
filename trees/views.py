from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.filters import InBBoxFilter
from .models import HH_Roadside
from flexibi_dst.models import Districts_HH
from .serializers import TreeSerializer

class TreeViewSet(ReadOnlyModelViewSet):
    bbox_filter_field = 'geom'
    filter_backends = (InBBoxFilter, )
    queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Erle', pflanzjahr__gt=1950, geom__intersects=Districts_HH.objects.get(name='Altona').geom)
    serializer_class = TreeSerializer