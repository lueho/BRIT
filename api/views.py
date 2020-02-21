from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.filters import InBBoxFilter
from .models import TreeCollection
from .serializers import TreeCollectioSerializer

class TreeCollectionViewSet(ReadOnlyModelViewSet):
    bbox_filter_field = 'location'
    filter_backends = (InBBoxFilter,)
    queryset = TreeCollection.objects.filter(location__isnuss=False)
    serializer_class = TreeCollectionSerializer