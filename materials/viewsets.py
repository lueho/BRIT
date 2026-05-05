from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.object_management.permissions import (
    UserCreatedObjectPermission,
    filter_queryset_for_user,
)

from .filters import (
    CompositionFilterSet,
    MaterialFilterSet,
    SampleFilterSet,
    SampleSeriesFilterSet,
)
from .models import Composition, Material, Sample, SampleSeries
from .serializers import (
    CompositionAPISerializer,
    MaterialAPISerializer,
    SampleAPISerializer,
    SampleSeriesAPISerializer,
)


class UserCreatedObjectReadOnlyViewSet(ReadOnlyModelViewSet):
    """Read-only base viewset that enforces UserCreatedObject visibility rules.

    list/retrieve are open to all users (including anonymous); the queryset
    filter restricts what each user can actually see:
    - staff: everything
    - anonymous: published only
    - authenticated: own objects + published
    - authenticated moderator: own + published + review

    Detail lookups fetch from the unfiltered base queryset and then enforce
    object-level permissions, consistent with UserCreatedObjectViewSet.
    """

    permission_classes = [UserCreatedObjectPermission]

    def get_queryset(self):
        return filter_queryset_for_user(self.queryset, self.request.user)

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        obj = get_object_or_404(self.queryset, **{self.lookup_field: lookup_value})
        self.check_object_permissions(self.request, obj)
        return obj


class MaterialViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialAPISerializer
    filterset_class = MaterialFilterSet


class CompositionViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionAPISerializer
    filterset_class = CompositionFilterSet


class SampleViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleAPISerializer
    filterset_class = SampleFilterSet


class SampleSeriesViewSet(UserCreatedObjectReadOnlyViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = SampleSeriesAPISerializer
    filterset_class = SampleSeriesFilterSet
