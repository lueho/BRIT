from rest_framework.viewsets import ReadOnlyModelViewSet

from .filters import CompositionFilterSet, MaterialFilterSet, SampleFilterSet, SampleSeriesFilterSet
from .models import Composition, Material, Sample, SampleSeries
from .serializers import CompositionAPISerializer, MaterialAPISerializer, SampleAPISerializer, SampleSeriesAPISerializer


class MaterialViewSet(ReadOnlyModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialAPISerializer
    filterset_class = MaterialFilterSet


class CompositionViewSet(ReadOnlyModelViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionAPISerializer
    filterset_class = CompositionFilterSet


class SampleViewSet(ReadOnlyModelViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleAPISerializer
    filterset_class = SampleFilterSet


class SampleSeriesViewSet(ReadOnlyModelViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = SampleSeriesAPISerializer
    filterset_class = SampleSeriesFilterSet
