"""ViewSets for the processes module REST API.

Provides RESTful API endpoints for all process-related models.
"""

from django.db.models import Count, Prefetch
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)
from .serializers import (
    ProcessCategorySerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessMaterialAPISerializer,
    ProcessOperatingParameterSerializer,
)


class ProcessCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for ProcessCategory CRUD operations."""

    queryset = ProcessCategory.objects.filter(publication_status="published")
    serializer_class = ProcessCategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Annotate with process counts."""
        queryset = super().get_queryset()
        return queryset.annotate(process_count=Count("processes"))

    @action(detail=True, methods=["get"])
    def processes(self, request, pk=None):
        """Get all processes in this category."""
        category = self.get_object()
        processes = category.processes.filter(publication_status="published")
        serializer = ProcessListSerializer(processes, many=True)
        return Response(serializer.data)


class ProcessViewSet(viewsets.ModelViewSet):
    """ViewSet for Process CRUD operations."""

    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_description", "mechanism", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Optimize queries with select/prefetch related."""
        queryset = Process.objects.filter(publication_status="published")
        
        if self.action == "list":
            queryset = queryset.select_related("owner", "parent").prefetch_related(
                "categories"
            )
        elif self.action == "retrieve":
            queryset = queryset.select_related("owner", "parent").prefetch_related(
                "categories",
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
                "references__source",
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
        return Response({
            "inputs": [
                {"id": m.id, "name": m.name}
                for m in process.input_materials
            ],
            "outputs": [
                {"id": m.id, "name": m.name}
                for m in process.output_materials
            ],
        })

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
            
            params_by_type[param_type].append({
                "id": param.id,
                "name": param.name if param.name else param_type,
                "value_min": param.value_min,
                "value_max": param.value_max,
                "nominal_value": param.nominal_value,
                "unit": param.unit.name if param.unit else None,
                "basis": param.basis,
            })
        
        return Response(params_by_type)

    @action(detail=True, methods=["get"])
    def variants(self, request, pk=None):
        """Get all process variants (children) of this process."""
        process = self.get_object()
        variants = process.variants.filter(publication_status="published")
        serializer = ProcessListSerializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def sources(self, request, pk=None):
        """Get all literature sources referenced by this process."""
        process = self.get_object()
        sources = [
            {
                "id": s.id,
                "title": s.title,
                "abbreviation": s.abbreviation,
                "type": s.type,
            }
            for s in process.sources
        ]
        return Response(sources)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get processes grouped by category."""
        categories = ProcessCategory.objects.filter(
            publication_status="published"
        ).prefetch_related("processes")
        
        result = []
        for category in categories:
            processes = category.processes.filter(publication_status="published")
            if processes.exists():
                result.append({
                    "category": ProcessCategorySerializer(category).data,
                    "processes": ProcessListSerializer(processes, many=True).data,
                })
        
        return Response(result)

    @action(detail=False, methods=["get"])
    def by_mechanism(self, request):
        """Get processes grouped by mechanism."""
        processes = self.get_queryset()
        
        mechanisms = {}
        for process in processes:
            mechanism = process.mechanism or "Other"
            if mechanism not in mechanisms:
                mechanisms[mechanism] = []
            mechanisms[mechanism].append(ProcessListSerializer(process).data)
        
        return Response(mechanisms)
