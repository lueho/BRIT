from utils.object_management.viewsets import UserCreatedObjectViewSet

from .filters import (
    CompositionFilterSet,
    MaterialFilterSet,
    SampleFilterSet,
    SampleSeriesFilterSet,
)
from .models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
)
from .serializers import (
    ComponentMeasurementReadSerializer,
    ComponentMeasurementWriteSerializer,
    CompositionAPISerializer,
    CompositionWriteSerializer,
    MaterialAPISerializer,
    MaterialPropertyValueReadSerializer,
    MaterialPropertyValueWriteSerializer,
    MaterialWriteSerializer,
    SampleAPISerializer,
    SampleSeriesAPISerializer,
    SampleSeriesWriteSerializer,
    SampleWriteSerializer,
)


class MaterialViewSet(UserCreatedObjectViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialAPISerializer
    filterset_class = MaterialFilterSet

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MaterialWriteSerializer
        return MaterialAPISerializer


class SampleSeriesViewSet(UserCreatedObjectViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = SampleSeriesAPISerializer
    filterset_class = SampleSeriesFilterSet

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SampleSeriesWriteSerializer
        return SampleSeriesAPISerializer


class SampleViewSet(UserCreatedObjectViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleAPISerializer
    filterset_class = SampleFilterSet

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SampleWriteSerializer
        return SampleAPISerializer


class CompositionViewSet(UserCreatedObjectViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionAPISerializer
    filterset_class = CompositionFilterSet

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CompositionWriteSerializer
        return CompositionAPISerializer


class ComponentMeasurementViewSet(UserCreatedObjectViewSet):
    queryset = ComponentMeasurement.objects.all()
    serializer_class = ComponentMeasurementReadSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ComponentMeasurementWriteSerializer
        return ComponentMeasurementReadSerializer


class MaterialPropertyValueViewSet(UserCreatedObjectViewSet):
    queryset = MaterialPropertyValue.objects.all()
    serializer_class = MaterialPropertyValueReadSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MaterialPropertyValueWriteSerializer
        return MaterialPropertyValueReadSerializer
