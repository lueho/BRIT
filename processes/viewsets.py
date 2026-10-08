"""ViewSets for the processes module REST API.

Provides RESTful API endpoints for all process-related models.
"""

from django.db.models import Prefetch
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from bibliography.models import Source
from materials.models import Material
from utils.object_management.permissions import (
    UserCreatedObjectPermission,
    filter_queryset_for_user,
)
from utils.object_management.viewsets import UserCreatedObjectViewSet

from .models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)
from .querysets import with_process_count
from .serializers import (
    ProcessCategorySerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessOperatingParameterSerializer,
)


class ProcessObjectPermission(UserCreatedObjectPermission):
    """Public read for all GET endpoints, policy-gated writes.

    ``UserCreatedObjectPermission`` only treats the plain ``list``/``retrieve``
    actions as publicly callable. The extra read actions below must stay
    reachable anonymously as well; object-level read checks still gate access
    to non-published objects in ``get_object``.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return super().has_permission(request, view)


def _shared_serializer_context(view):
    """Serializer context with a shared visibility cache for related objects.

    Calls ``GenericAPIView.get_serializer_context`` directly so it can also be
    used inside a view's own ``get_serializer_context`` override without
    recursing.
    """
    from rest_framework.generics import GenericAPIView

    return {
        **GenericAPIView.get_serializer_context(view),
        "visible_pks_cache": {},
    }


def _visible_categories_queryset(user):
    """Categories readable by ``user`` annotated with their visible process count."""
    return with_process_count(
        filter_queryset_for_user(ProcessCategory.objects.all(), user), user=user
    )


class ProcessCategoryViewSet(UserCreatedObjectViewSet):
    """ViewSet for ProcessCategory CRUD operations."""

    queryset = ProcessCategory.objects.all()
    serializer_class = ProcessCategorySerializer
    permission_classes = [ProcessObjectPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "lastmodified_at"]
    ordering = ["name"]

    def _annotate_process_count(self, queryset):
        # Count processes readable by the requester so the number matches
        # what the requester could fetch via the ``processes`` action.
        return with_process_count(queryset, user=self.request.user)

    def get_queryset(self):
        return self._annotate_process_count(super().get_queryset())

    def get_object(self):
        # The base implementation reads ``self.queryset`` directly rather than
        # going through ``get_queryset``; annotate it so detail responses also
        # carry the request-scoped process_count.
        self.queryset = self._annotate_process_count(self.queryset)
        return super().get_object()

    @action(detail=True, methods=["get"])
    def processes(self, request, pk=None):
        """Get all processes in this category readable by the requester."""
        category = self.get_object()
        processes = filter_queryset_for_user(
            category.processes.all(), request.user
        ).prefetch_related("categories", "sources")
        serializer = ProcessListSerializer(
            processes, many=True, context=_shared_serializer_context(self)
        )
        return Response(serializer.data)


class ProcessViewSet(UserCreatedObjectViewSet):
    """ViewSet for Process CRUD operations."""

    queryset = Process.objects.all()
    permission_classes = [ProcessObjectPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_description", "mechanism", "description"]
    ordering_fields = ["name", "created_at", "lastmodified_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Optimize queries with select/prefetch related."""
        queryset = super().get_queryset()
        user = self.request.user

        if self.action == "list":
            queryset = queryset.select_related("owner").prefetch_related(
                Prefetch(
                    "categories",
                    queryset=filter_queryset_for_user(
                        ProcessCategory.objects.all(), user
                    ),
                ),
                Prefetch(
                    "sources",
                    queryset=filter_queryset_for_user(
                        Source.objects.all(), user
                    ),
                ),
            )
        elif self.action == "retrieve":
            queryset = queryset.select_related("owner").prefetch_related(
                Prefetch(
                    "categories",
                    queryset=filter_queryset_for_user(
                        ProcessCategory.objects.all(), user
                    ),
                ),
                Prefetch(
                    "process_materials",
                    queryset=ProcessMaterial.objects.select_related(
                        "material", "quantity_unit"
                    ).filter(
                        material__in=filter_queryset_for_user(
                            Material.objects.all(), user
                        )
                    ),
                ),
                Prefetch(
                    "operating_parameters",
                    queryset=ProcessOperatingParameter.objects.select_related("unit"),
                ),
                "links",
                "info_resources",
                Prefetch(
                    "sources",
                    queryset=filter_queryset_for_user(
                        Source.objects.all(), user
                    ),
                ),
            )

        return queryset

    def get_serializer_context(self):
        return _shared_serializer_context(self)

    def get_serializer_class(self):
        """Use different serializers for list and detail views."""
        if self.action == "list":
            return ProcessListSerializer
        return ProcessDetailSerializer

    @action(detail=True, methods=["get"])
    def materials(self, request, pk=None):
        """Get all materials (inputs and outputs) for this process."""
        process = self.get_object()
        visible = set(
            filter_queryset_for_user(
                Material.objects.all(), request.user
            ).values_list("pk", flat=True)
        )
        return Response(
            {
                "inputs": [
                    {"id": m.id, "name": m.name}
                    for m in process.input_materials
                    if m.pk in visible
                ],
                "outputs": [
                    {"id": m.id, "name": m.name}
                    for m in process.output_materials
                    if m.pk in visible
                ],
            }
        )

    @action(detail=True, methods=["get"])
    def parameters(self, request, pk=None):
        """Get all operating parameters for this process."""
        process = self.get_object()
        parameters = process.operating_parameters.all()
        serializer = ProcessOperatingParameterSerializer(parameters, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def parameters_by_type(self, request, pk=None):
        """Get operating parameters grouped by type."""
        process = self.get_object()

        params_by_type = {}
        for param in process.operating_parameters.all():
            param_type = param.get_parameter_display()
            if param_type not in params_by_type:
                params_by_type[param_type] = []

            params_by_type[param_type].append(
                {
                    "id": param.id,
                    "name": param.name if param.name else param_type,
                    "value_min": param.value_min,
                    "value_max": param.value_max,
                    "nominal_value": param.nominal_value,
                    "unit": param.unit.name if param.unit else None,
                    "basis": param.basis,
                }
            )

        return Response(params_by_type)

    @action(detail=True, methods=["get"])
    def sources(self, request, pk=None):
        """Get all literature sources referenced by this process."""
        process = self.get_object()
        visible = set(
            filter_queryset_for_user(
                Source.objects.all(), request.user
            ).values_list("pk", flat=True)
        )
        sources = [
            {
                "id": s.id,
                "title": s.title,
                "abbreviation": s.abbreviation,
                "type": s.type,
            }
            for s in process.sources_ordered()
            if s.pk in visible
        ]
        return Response(sources)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get processes grouped by category, scoped to the requester's visibility."""
        categories = _visible_categories_queryset(request.user).prefetch_related(
            Prefetch(
                "processes",
                queryset=filter_queryset_for_user(
                    Process.objects.all(), request.user
                ).prefetch_related("categories", "sources"),
            )
        )

        context = _shared_serializer_context(self)
        result = []
        for category in categories:
            processes = list(category.processes.all())
            if processes:
                result.append(
                    {
                        "category": ProcessCategorySerializer(
                            category, context=context
                        ).data,
                        "processes": ProcessListSerializer(
                            processes, many=True, context=context
                        ).data,
                    }
                )

        return Response(result)

    @action(detail=False, methods=["get"])
    def by_mechanism(self, request):
        """Get processes grouped by mechanism."""
        processes = self.get_queryset().prefetch_related("categories", "sources")
        context = _shared_serializer_context(self)

        mechanisms = {}
        for process in processes:
            mechanism = process.mechanism or "Other"
            if mechanism not in mechanisms:
                mechanisms[mechanism] = []
            mechanisms[mechanism].append(
                ProcessListSerializer(process, context=context).data
            )

        return Response(mechanisms)
