from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.properties.serializers import PropertyModelSerializer, PropertyUnitModelSerializer
from .models import Property, PropertyUnit


class PropertyUnitViewSet(ReadOnlyModelViewSet):
    queryset = PropertyUnit.objects.all()
    serializer_class = PropertyUnitModelSerializer


class PropertyViewSet(ReadOnlyModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertyModelSerializer
