"""Serializers for the processes module.

Provides REST API serializers for all process-related models.
"""

from rest_framework import serializers

from bibliography.models import Author, Source
from bibliography.serializers import SourceModelSerializer
from materials.models import Material
from materials.serializers import MaterialAPISerializer
from utils.object_management.permissions import filter_queryset_for_user
from utils.properties.models import Unit
from utils.properties.serializers import UnitModelSerializer

from .models import (
    Process,
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
)


class ProcessCategorySerializer(serializers.ModelSerializer):
    """Serializer for ProcessCategory."""

    process_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProcessCategory
        fields = [
            "id",
            "name",
            "description",
            "publication_status",
            "owner",
            "created_at",
            "lastmodified_at",
            "process_count",
        ]
        read_only_fields = [
            "owner",
            "publication_status",
            "created_at",
            "lastmodified_at",
        ]


class ProcessCategoryReferenceSerializer(serializers.ModelSerializer):
    """Category nested inside process payloads.

    ``process_count`` is only annotated on category viewset querysets, so the
    nested representation deliberately omits it to keep the response shape
    stable regardless of which queryset produced the objects.
    """

    class Meta:
        model = ProcessCategory
        fields = ["id", "name", "description", "publication_status"]


class ProcessMaterialAPISerializer(serializers.ModelSerializer):
    """Serializer for ProcessMaterial."""

    material = MaterialAPISerializer(read_only=True)
    material_id = serializers.PrimaryKeyRelatedField(
        source="material",
        queryset=Material.objects.all(),
        write_only=True,
    )
    quantity_unit = UnitModelSerializer(read_only=True)
    quantity_unit_id = serializers.PrimaryKeyRelatedField(
        source="quantity_unit",
        queryset=Unit.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = ProcessMaterial
        fields = [
            "id",
            "process",
            "material",
            "material_id",
            "role",
            "role_display",
            "order",
            "stage",
            "stream_label",
            "quantity_value",
            "quantity_unit",
            "quantity_unit_id",
            "notes",
            "optional",
        ]
        read_only_fields = ["process"]


class ProcessOperatingParameterSerializer(serializers.ModelSerializer):
    """Serializer for ProcessOperatingParameter."""

    unit = UnitModelSerializer(read_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(
        source="unit",
        queryset=Unit.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    parameter_display = serializers.CharField(
        source="get_parameter_display", read_only=True
    )

    class Meta:
        model = ProcessOperatingParameter
        fields = [
            "id",
            "process",
            "parameter",
            "parameter_display",
            "name",
            "unit",
            "unit_id",
            "value_min",
            "value_max",
            "nominal_value",
            "basis",
            "notes",
            "order",
        ]
        read_only_fields = ["process"]


class ProcessLinkSerializer(serializers.ModelSerializer):
    """Serializer for ProcessLink."""

    class Meta:
        model = ProcessLink
        fields = [
            "id",
            "process",
            "label",
            "url",
            "open_in_new_tab",
            "order",
        ]
        read_only_fields = ["process"]


class ProcessInfoResourceSerializer(serializers.ModelSerializer):
    """Serializer for ProcessInfoResource."""

    resource_type_display = serializers.CharField(
        source="get_resource_type_display", read_only=True
    )
    target_url = serializers.CharField(read_only=True)

    class Meta:
        model = ProcessInfoResource
        fields = [
            "id",
            "process",
            "title",
            "resource_type",
            "resource_type_display",
            "description",
            "url",
            "document",
            "target_url",
            "order",
        ]
        read_only_fields = ["process", "target_url"]


class ScopedRelatedObjectsMixin:
    """Hide related objects the requesting user may not read.

    ``_visible_pks`` resolves the readable pk set per related model once per
    request; viewsets share it across serialized rows via the
    ``visible_pks_cache`` context key.
    """

    def _visible_pks(self, model):
        cache = self.context.get("visible_pks_cache")
        if cache is None:
            cache = getattr(self, "_visible_pks_cache", None)
            if cache is None:
                cache = self._visible_pks_cache = {}
        key = model._meta.label_lower
        if key not in cache:
            request = self.context.get("request")
            cache[key] = set(
                filter_queryset_for_user(
                    model.objects.all(), getattr(request, "user", None)
                ).values_list("pk", flat=True)
            )
        return cache[key]

    def _visible_material_links(self, obj):
        visible = self._visible_pks(Material)
        return [
            link for link in obj.process_materials.all() if link.material_id in visible
        ]


class ProcessListSerializer(ScopedRelatedObjectsMixin, serializers.ModelSerializer):
    """Simplified serializer for Process list views."""

    categories = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Process
        fields = [
            "id",
            "name",
            "categories",
            "short_description",
            "authors",
            "sources",
            "mechanism",
            "image",
            "publication_status",
            "owner",
            "owner_name",
            "created_at",
            "lastmodified_at",
        ]
        read_only_fields = [
            "owner",
            "publication_status",
            "created_at",
            "lastmodified_at",
        ]

    def get_categories(self, obj):
        visible = self._visible_pks(ProcessCategory)
        return ProcessCategoryReferenceSerializer(
            [c for c in obj.categories.all() if c.pk in visible], many=True
        ).data

    def get_sources(self, obj):
        visible = self._visible_pks(Source)
        return SourceModelSerializer(
            [s for s in obj.sources.all() if s.pk in visible], many=True
        ).data

    def get_authors(self, obj):
        """Get author ids in explicit process author order."""

        visible = self._visible_pks(Author)
        return [a.pk for a in obj.authors_ordered() if a.pk in visible]


class ProcessDetailSerializer(ScopedRelatedObjectsMixin, serializers.ModelSerializer):
    """Comprehensive serializer for Process detail views."""

    categories = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.username", read_only=True)

    # Related objects
    process_materials = serializers.SerializerMethodField()
    operating_parameters = ProcessOperatingParameterSerializer(
        many=True, read_only=True
    )
    links = ProcessLinkSerializer(many=True, read_only=True)
    info_resources = ProcessInfoResourceSerializer(many=True, read_only=True)

    # Convenience properties
    input_materials = serializers.SerializerMethodField()
    output_materials = serializers.SerializerMethodField()

    class Meta:
        model = Process
        fields = [
            "id",
            "name",
            "categories",
            "short_description",
            "authors",
            "mechanism",
            "description",
            "process_technology",
            "image",
            "publication_status",
            "owner",
            "owner_name",
            "created_at",
            "lastmodified_at",
            # Related objects
            "process_materials",
            "operating_parameters",
            "links",
            "info_resources",
            # Convenience fields
            "input_materials",
            "output_materials",
            "sources",
        ]
        read_only_fields = [
            "owner",
            "publication_status",
            "created_at",
            "lastmodified_at",
        ]

    def get_categories(self, obj):
        visible = self._visible_pks(ProcessCategory)
        return ProcessCategoryReferenceSerializer(
            [c for c in obj.categories.all() if c.pk in visible], many=True
        ).data

    def get_sources(self, obj):
        visible = self._visible_pks(Source)
        return SourceModelSerializer(
            [s for s in obj.sources.all() if s.pk in visible], many=True
        ).data

    def get_authors(self, obj):
        """Get author ids in explicit process author order."""

        visible = self._visible_pks(Author)
        return [a.pk for a in obj.authors_ordered() if a.pk in visible]

    def get_process_materials(self, obj):
        return ProcessMaterialAPISerializer(
            self._visible_material_links(obj), many=True, context=self.context
        ).data

    def get_input_materials(self, obj):
        """Get list of input materials."""
        visible = self._visible_pks(Material)
        return [
            {"id": m.id, "name": m.name} for m in obj.input_materials if m.pk in visible
        ]

    def get_output_materials(self, obj):
        """Get list of output materials."""
        visible = self._visible_pks(Material)
        return [
            {"id": m.id, "name": m.name}
            for m in obj.output_materials
            if m.pk in visible
        ]
