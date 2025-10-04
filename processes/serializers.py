"""Serializers for the processes module.

Provides REST API serializers for all process-related models.
"""

from rest_framework import serializers

from bibliography.serializers import SourceModelSerializer
from materials.serializers import MaterialAPISerializer
from utils.properties.serializers import UnitModelSerializer

from .models import (
    Process,
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessReference,
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
            "updated_at",
            "process_count",
        ]
        read_only_fields = ["owner", "created_at", "updated_at"]


class ProcessMaterialAPISerializer(serializers.ModelSerializer):
    """Serializer for ProcessMaterial."""

    material = MaterialAPISerializer(read_only=True)
    material_id = serializers.PrimaryKeyRelatedField(
        source="material",
        queryset=serializers.SerializerMethodField(),
        write_only=True,
    )
    quantity_unit = UnitModelSerializer(read_only=True)
    quantity_unit_id = serializers.PrimaryKeyRelatedField(
        source="quantity_unit",
        queryset=serializers.SerializerMethodField(),
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
        queryset=serializers.SerializerMethodField(),
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


class ProcessReferenceSerializer(serializers.ModelSerializer):
    """Serializer for ProcessReference."""

    source = SourceModelSerializer(read_only=True)
    source_id = serializers.PrimaryKeyRelatedField(
        source="source",
        queryset=serializers.SerializerMethodField(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProcessReference
        fields = [
            "id",
            "process",
            "source",
            "source_id",
            "title",
            "url",
            "reference_type",
            "order",
        ]
        read_only_fields = ["process"]


class ProcessListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Process list views."""

    categories = ProcessCategorySerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = Process
        fields = [
            "id",
            "name",
            "parent",
            "parent_name",
            "categories",
            "short_description",
            "mechanism",
            "image",
            "publication_status",
            "owner",
            "owner_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "created_at", "updated_at"]


class ProcessDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for Process detail views."""

    categories = ProcessCategorySerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    
    # Related objects
    process_materials = ProcessMaterialAPISerializer(many=True, read_only=True)
    operating_parameters = ProcessOperatingParameterSerializer(many=True, read_only=True)
    links = ProcessLinkSerializer(many=True, read_only=True)
    info_resources = ProcessInfoResourceSerializer(many=True, read_only=True)
    references = ProcessReferenceSerializer(many=True, read_only=True)
    
    # Convenience properties
    input_materials = serializers.SerializerMethodField()
    output_materials = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()

    class Meta:
        model = Process
        fields = [
            "id",
            "name",
            "parent",
            "parent_name",
            "categories",
            "short_description",
            "mechanism",
            "description",
            "image",
            "publication_status",
            "owner",
            "owner_name",
            "created_at",
            "updated_at",
            # Related objects
            "process_materials",
            "operating_parameters",
            "links",
            "info_resources",
            "references",
            # Convenience fields
            "input_materials",
            "output_materials",
            "sources",
        ]
        read_only_fields = ["owner", "created_at", "updated_at"]

    def get_input_materials(self, obj):
        """Get list of input materials."""
        return [
            {"id": m.id, "name": m.name}
            for m in obj.input_materials
        ]

    def get_output_materials(self, obj):
        """Get list of output materials."""
        return [
            {"id": m.id, "name": m.name}
            for m in obj.output_materials
        ]

    def get_sources(self, obj):
        """Get distinct literature sources."""
        return [
            {"id": s.id, "title": s.title, "abbreviation": s.abbreviation}
            for s in obj.sources
        ]
