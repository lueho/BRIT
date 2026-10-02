"""ViewSets for the processes module REST API.

Provides RESTful API endpoints for all process-related models.
"""

from django.db.models import Exists, OuterRef, Prefetch
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from bibliography.models import Author, Licence, Source
from utils.object_management.permissions import (
    UserCreatedObjectPermission,
    filter_queryset_for_user,
)
from utils.object_management.viewsets import UserCreatedObjectViewSet

from .models import (
    Process,
    ProcessAuthor,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)
from .querysets import with_published_process_count
from .serializers import (
    ProcessCategorySerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessOperatingParameterSerializer,
)


def _visible_process_relations(queryset, user):
    """Prefetch nested relations through the read policy.

    ``ProcessListSerializer``/``ProcessDetailSerializer`` serialize nested
    categories, sources and the parent name. Without a filtered prefetch the
    related managers would expose objects the user may not read. The
    ``parent_is_visible`` annotation lets the serializer resolve the parent
    name without a per-object policy query.
    """

    return queryset.prefetch_related(
        Prefetch(
            "categories",
            queryset=filter_queryset_for_user(ProcessCategory.objects.all(), user),
        ),
        Prefetch(
            "sources",
            queryset=filter_queryset_for_user(Source.objects.all(), user)
            .select_related("licence")
            .prefetch_related(
                Prefetch(
                    "authors",
                    queryset=filter_queryset_for_user(Author.objects.all(), user),
                )
            )
            .annotate(
                licence_is_visible=Exists(
                    filter_queryset_for_user(
                        Licence.objects.filter(pk=OuterRef("licence_id")),
                        user,
                    )
                )
            ),
        ),
        Prefetch(
            "process_authors",
            queryset=ProcessAuthor.objects.filter(
                author__in=filter_queryset_for_user(Author.objects.all(), user)
            )
            .select_related("author")
            .order_by("position", "author_id", "id"),
        ),
    ).annotate(
        parent_is_visible=Exists(
            filter_queryset_for_user(
                Process.objects.filter(pk=OuterRef("parent_id")), user
            )
        )
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


class ProcessCategoryViewSet(UserCreatedObjectViewSet):
    """ViewSet for ProcessCategory CRUD operations."""

    queryset = with_published_process_count(ProcessCategory.objects.all())
    serializer_class = ProcessCategorySerializer
    permission_classes = [ProcessObjectPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get"])
    def processes(self, request, pk=None):
        """Get all processes in this category visible to the current user."""
        category = self.get_object()
        processes = _visible_process_relations(
            filter_queryset_for_user(
                category.processes.all(), request.user
            ).select_related("owner", "parent"),
            request.user,
        )
        serializer = ProcessListSerializer(
            processes, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)


class ProcessViewSet(UserCreatedObjectViewSet):
    """ViewSet for Process CRUD operations."""

    queryset = Process.objects.all()
    permission_classes = [ProcessObjectPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_description", "mechanism", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Optimize queries with select/prefetch related."""
        queryset = super().get_queryset()

        if self.action in ("list", "by_mechanism"):
            queryset = _visible_process_relations(
                queryset.select_related("owner", "parent"), self.request.user
            )
        elif self.action == "retrieve":
            queryset = _visible_process_relations(
                queryset.select_related("owner", "parent"), self.request.user
            ).prefetch_related(
                "variants",
                Prefetch(
                    "process_materials",
                    queryset=ProcessMaterial.objects.select_related(
                        "material", "quantity_unit"
                    ),
                ),
                Prefetch(
                    "operating_parameters",
                    queryset=ProcessOperatingParameter.objects.select_related("unit"),
                ),
                "links",
                "info_resources",
            )

        return queryset

    def get_serializer_class(self):
        """Use different serializers for list and detail views."""
        if self.action == "list":
            return ProcessListSerializer
        return ProcessDetailSerializer

    @action(detail=True, methods=["get"])
    def materials(self, request, pk=None):
        """Get all materials (inputs and outputs) for this process."""
        process = self.get_object()
        serializer = self.get_serializer(process)
        return Response(
            {
                "inputs": serializer.data["input_materials"],
                "outputs": serializer.data["output_materials"],
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
    def variants(self, request, pk=None):
        """Get all process variants (children) visible to the current user."""
        process = self.get_object()
        variants = _visible_process_relations(
            filter_queryset_for_user(process.variants.all(), request.user),
            request.user,
        )
        serializer = ProcessListSerializer(
            variants, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def sources(self, request, pk=None):
        """Get all literature sources referenced by this process."""
        process = self.get_object()
        ordered = list(process.sources_ordered())
        visible_ids = set(
            filter_queryset_for_user(
                Source.objects.filter(pk__in=[s.pk for s in ordered]),
                request.user,
            ).values_list("pk", flat=True)
        )
        sources = [
            {
                "id": s.id,
                "title": s.title,
                "abbreviation": s.abbreviation,
                "type": s.type,
            }
            for s in ordered
            if s.pk in visible_ids
        ]
        return Response(sources)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get processes grouped by category, scoped to what the user may read."""
        visible_processes = _visible_process_relations(
            filter_queryset_for_user(
                Process.objects.all(), request.user
            ).select_related("owner", "parent"),
            request.user,
        )
        categories = filter_queryset_for_user(
            ProcessCategory.objects.all(), request.user
        ).prefetch_related(Prefetch("processes", queryset=visible_processes))

        serializer_context = self.get_serializer_context()
        result = []
        for category in categories:
            processes = list(category.processes.all())
            if processes:
                result.append(
                    {
                        "category": ProcessCategorySerializer(
                            category, context=serializer_context
                        ).data,
                        "processes": ProcessListSerializer(
                            processes,
                            many=True,
                            context=serializer_context,
                        ).data,
                    }
                )

        return Response(result)

    @action(detail=False, methods=["get"])
    def by_mechanism(self, request):
        """Get processes grouped by mechanism."""
        processes = self.get_queryset()
        serialized = ProcessListSerializer(
            processes, many=True, context=self.get_serializer_context()
        ).data

        mechanisms = {}
        for process, data in zip(processes, serialized, strict=True):
            mechanisms.setdefault(process.mechanism or "Other", []).append(data)

        return Response(mechanisms)
