from rest_framework.exceptions import PermissionDenied

from utils.object_management.viewsets import UserCreatedObjectViewSet
from utils.viewsets import ReadWriteSerializerViewSetMixin

from .filters import (
    CompositionFilterSet,
    MaterialFilterSet,
    SampleFilterSet,
    SampleGroupFilterSet,
    SampleSeriesFilterSet,
)
from .models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialPropertyValue,
    Sample,
    SampleGroup,
    SampleSeries,
)
from .permissions import can_add_data_to_sample
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
    SampleGroupAPISerializer,
    SampleGroupWriteSerializer,
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
        previous_sample_id = instance.sample_id if instance is not None else None
        if not can_add_data_to_sample(
            self.request.user,
            sample,
            previous_sample_id,
            self.sample_policy_key,
            request=self.request,
        ):
            raise PermissionDenied("You cannot add data to this sample.")

    def perform_create(self, serializer):
        self._validate_target_sample(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._validate_target_sample(serializer)
        super().perform_update(serializer)


class MaterialViewSet(ReadWriteSerializerViewSetMixin, UserCreatedObjectViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialAPISerializer
    write_serializer_class = MaterialWriteSerializer
    filterset_class = MaterialFilterSet


class SampleSeriesViewSet(ReadWriteSerializerViewSetMixin, UserCreatedObjectViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = SampleSeriesAPISerializer
    write_serializer_class = SampleSeriesWriteSerializer
    filterset_class = SampleSeriesFilterSet


class SampleGroupViewSet(ReadWriteSerializerViewSetMixin, UserCreatedObjectViewSet):
    queryset = SampleGroup.objects.all()
    serializer_class = SampleGroupAPISerializer
    write_serializer_class = SampleGroupWriteSerializer
    filterset_class = SampleGroupFilterSet


class SampleViewSet(ReadWriteSerializerViewSetMixin, UserCreatedObjectViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleAPISerializer
    write_serializer_class = SampleWriteSerializer
    filterset_class = SampleFilterSet


class CompositionViewSet(
    ReadWriteSerializerViewSetMixin,
    SampleBoundMutationViewSetMixin,
    UserCreatedObjectViewSet,
):
    queryset = Composition.objects.all()
    serializer_class = CompositionAPISerializer
    write_serializer_class = CompositionWriteSerializer
    filterset_class = CompositionFilterSet
    sample_policy_key = "can_manage_samples"


class ComponentMeasurementViewSet(
    ReadWriteSerializerViewSetMixin,
    SampleBoundMutationViewSetMixin,
    UserCreatedObjectViewSet,
):
    queryset = ComponentMeasurement.objects.all()
    serializer_class = ComponentMeasurementReadSerializer
    write_serializer_class = ComponentMeasurementWriteSerializer
    sample_policy_key = "can_manage_samples"


class MaterialPropertyValueViewSet(
    ReadWriteSerializerViewSetMixin,
    SampleBoundMutationViewSetMixin,
    UserCreatedObjectViewSet,
):
    queryset = MaterialPropertyValue.objects.all()
    serializer_class = MaterialPropertyValueReadSerializer
    write_serializer_class = MaterialPropertyValueWriteSerializer
    sample_policy_key = "can_add_property"
