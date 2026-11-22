from utils.object_management.viewsets import UserCreatedObjectReadOnlyViewSet
from utils.properties.serializers import PropertyModelSerializer, UnitModelSerializer

from .models import Property, Unit


class UnitViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitModelSerializer


class PropertyViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertyModelSerializer
