"""Serializers for the processes module.

Provides REST API serializers for all process-related models.
"""

from rest_framework import serializers

from bibliography.models import Author, Licence
from bibliography.serializers import (
    AuthorModelSerializer,
    LicenceModelSerializer,
    SourceModelSerializer,
)
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


class VisibleSourceSerializer(SourceModelSerializer):
    """Source serialization that hides relations the user may not read.

    Nested ``authors`` and ``licence`` are user-created objects; a visible
    source may still link private ones owned by someone else.
    """

    authors = serializers.SerializerMethodField()
    licence = serializers.SerializerMethodField()
    citation_key = serializers.SerializerMethodField()

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_citation_key(self, obj):
        """Citation keys embed author surnames; hide them while an author is hidden."""
        hidden = getattr(obj, "has_hidden_authors", None)
        if hidden is None:
            hidden = obj.authors.exclude(
                pk__in=filter_queryset_for_user(Author.objects.all(), self._user())
            ).exists()
        return None if hidden else obj.citation_key

    def get_authors(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", {})
        if "authors" in cache:
            authors = cache["authors"]
        else:
            authors = filter_queryset_for_user(obj.authors.all(), self._user())
        return AuthorModelSerializer(authors, many=True).data

    def get_licence(self, obj):
        if obj.licence_id is None:
            return None
        visible = getattr(obj, "licence_is_visible", None)
        if visible is None:
            visible = filter_queryset_for_user(
                Licence.objects.filter(pk=obj.licence_id), self._user()
            ).exists()
        return LicenceModelSerializer(obj.licence).data if visible else None


def visible_process_material_links(process, user):
    """ProcessMaterial links for ``process`` whose material ``user`` may read.

    Uses the prefetched link cache when present (already ``select_related`` on
    material), otherwise loads the links with their materials in one query.
    """
    cache = getattr(process, "_prefetched_objects_cache", {})
    if "process_materials" in cache:
        links = list(cache["process_materials"])
    else:
        links = list(process.process_materials.select_related("material"))
    visible_ids = set(
        filter_queryset_for_user(
            Material.objects.filter(pk__in={link.material_id for link in links}),
            user,
        ).values_list("pk", flat=True)
    )
    return [link for link in links if link.material_id in visible_ids]


class ProcessVisibilityMixin:
    """Applies the central read policy to nested user-created relations.

    The viewsets prefetch these relations with visibility-filtered querysets,
    so the prefetched cache already contains only visible rows. The fallback
    path applies ``filter_queryset_for_user`` to the relation directly.
    """

    def _request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _visible_related(self, obj, related_name):
        cache = getattr(obj, "_prefetched_objects_cache", {})
        if related_name in cache:
            return list(cache[related_name])
        return filter_queryset_for_user(
            getattr(obj, related_name).all(), self._request_user()
        )

    def _visible_process_materials(self, obj):
        """ProcessMaterial rows whose material is visible to the request user."""

        cache = getattr(self, "_pm_cache", None)
        if cache is None:
            cache = self._pm_cache = {}
        if obj.pk not in cache:
            cache[obj.pk] = visible_process_material_links(obj, self._request_user())
        return cache[obj.pk]

    def get_categories(self, obj):
        return ProcessCategorySerializer(
            self._visible_related(obj, "categories"), many=True
        ).data

    def get_sources(self, obj):
        return VisibleSourceSerializer(
            self._visible_related(obj, "sources"),
            many=True,
            context=self.context,
        ).data

    def get_authors(self, obj):
        """Get author ids in explicit process author order, read-policy scoped."""

        cache = getattr(obj, "_prefetched_objects_cache", {})
        if "process_authors" in cache:
            return [link.author_id for link in cache["process_authors"]]
        authors = obj.authors_ordered()
        if not authors:
            return []
        visible_ids = set(
            filter_queryset_for_user(
                Author.objects.filter(pk__in=[a.pk for a in authors]),
                self._request_user(),
            ).values_list("pk", flat=True)
        )
        return [a.pk for a in authors if a.pk in visible_ids]

    def get_parent_name(self, obj):
        if obj.parent_id is None:
            return None
        annotated = getattr(obj, "parent_is_visible", None)
        if annotated is not None:
            return obj.parent.name if annotated else None
        parent_visible = filter_queryset_for_user(
            Process.objects.filter(pk=obj.parent_id), self._request_user()
        ).exists()
        return obj.parent.name if parent_visible else None


class ProcessListSerializer(ProcessVisibilityMixin, serializers.ModelSerializer):
    """Simplified serializer for Process list views."""

    categories = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    parent_name = serializers.SerializerMethodField()

    class Meta:
        model = Process
        fields = [
            "id",
            "name",
            "parent",
            "parent_name",
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


class ProcessDetailSerializer(ProcessListSerializer):
    """Comprehensive serializer for Process detail views."""

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

    class Meta(ProcessListSerializer.Meta):
        fields = [
            *ProcessListSerializer.Meta.fields,
            "description",
            "process_technology",
            # Related objects
            "process_materials",
            "operating_parameters",
            "links",
            "info_resources",
            # Convenience fields
            "input_materials",
            "output_materials",
        ]

    def get_process_materials(self, obj):
        return ProcessMaterialAPISerializer(
            self._visible_process_materials(obj), many=True
        ).data

    def _materials_for_role(self, obj, role):
        return [
            {"id": link.material_id, "name": link.material.name}
            for link in self._visible_process_materials(obj)
            if link.role == role
        ]

    def get_input_materials(self, obj):
        """Get list of input materials."""
        return self._materials_for_role(obj, ProcessMaterial.Role.INPUT)

    def get_output_materials(self, obj):
        """Get list of output materials."""
        return self._materials_for_role(obj, ProcessMaterial.Role.OUTPUT)
