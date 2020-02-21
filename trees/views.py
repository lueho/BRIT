from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.filters import InBBoxFilter
from .models import HH_Roadside
from .serializers import TreeSerializer

class TreeViewSet(ReadOnlyModelViewSet):
    bbox_filter_field = 'geom'
    filter_backends = (InBBoxFilter, )
    queryset = HH_Roadside.objects.filter(geom__isnull=False, gattung_deutsch='Eiche', bezirk='Altona')
    serializer_class = TreeSerializer