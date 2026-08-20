from rest_framework.exceptions import PermissionDenied

from utils.object_management.permissions import get_object_policy
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


class SampleBoundMutationViewSetMixin:
    sample_policy_key = None

    def _validate_target_sample(self, serializer):
        if "sample" not in serializer.validated_data:
            return

        sample = serializer.validated_data["sample"]
        instance = serializer.instance
        if sample is None or (instance is not None and instance.sample_id == sample.pk):
            return

        policy = get_object_policy(self.request.user, sample, request=self.request)
        if not policy[self.sample_policy_key]:
            raise PermissionDenied("You cannot add data to this sample.")

    def perform_create(self, serializer):
        self._validate_target_sample(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._validate_target_sample(serializer)
        super().perform_update(serializer)


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


class CompositionViewSet(SampleBoundMutationViewSetMixin, UserCreatedObjectViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionAPISerializer
    filterset_class = CompositionFilterSet
    sample_policy_key = "can_manage_samples"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CompositionWriteSerializer
        return CompositionAPISerializer


class ComponentMeasurementViewSet(
    SampleBoundMutationViewSetMixin, UserCreatedObjectViewSet
):
    queryset = ComponentMeasurement.objects.all()
    serializer_class = ComponentMeasurementReadSerializer
    sample_policy_key = "can_manage_samples"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ComponentMeasurementWriteSerializer
        return ComponentMeasurementReadSerializer


class MaterialPropertyValueViewSet(
    SampleBoundMutationViewSetMixin, UserCreatedObjectViewSet
):
    queryset = MaterialPropertyValue.objects.all()
    serializer_class = MaterialPropertyValueReadSerializer
    sample_policy_key = "can_add_property"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MaterialPropertyValueWriteSerializer
        return MaterialPropertyValueReadSerializer
