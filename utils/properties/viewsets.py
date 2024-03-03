from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.properties.serializers import PropertyModelSerializer, UnitModelSerializer
from .models import Property, Unit


class UnitViewSet(ReadOnlyModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitModelSerializer


class PropertyViewSet(ReadOnlyModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertyModelSerializer
