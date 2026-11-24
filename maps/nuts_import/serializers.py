"""Serializers implementing the versioned NUTS vintage import contract."""

from rest_framework import serializers

from maps.import_common import GeometryField

from .contracts import SCHEMA_VERSION


class ImportVintageSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=1990, max_value=2100)
    source_release = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    is_current = serializers.BooleanField(required=False, default=False)


class ImportRegionSerializer(serializers.Serializer):
    """One region of a vintage.

    Optional fields carry no defaults on purpose: an omitted field means "leave
    what BRIT holds", which a default would turn into "blank it".
    """

    nuts_id = serializers.CharField(max_length=5)
    # Codes are positional, but not always: NUTS 2016 files UKN10-UKN16 under
    # UKN0, so a provider may name the parent instead.
    parent_nuts_id = serializers.CharField(
        max_length=5, required=False, allow_blank=True
    )
    levl_code = serializers.IntegerField(min_value=0, max_value=3)
    cntr_code = serializers.CharField(max_length=2)
    name_latn = serializers.CharField(max_length=70, required=False, allow_blank=True)
    nuts_name = serializers.CharField(max_length=106, required=False, allow_blank=True)
    name_en = serializers.CharField(max_length=113, required=False, allow_blank=True)
    mount_type = serializers.IntegerField(required=False, allow_null=True)
    urbn_type = serializers.IntegerField(required=False, allow_null=True)
    coast_type = serializers.IntegerField(required=False, allow_null=True)
    geometry = GeometryField(required=False, allow_null=True)


class NutsImportSerializer(serializers.Serializer):
    """Top-level provider-neutral import payload (``schema_version`` 1.0)."""

    schema_version = serializers.CharField()
    dry_run = serializers.BooleanField(required=False, default=False)
    vintage = ImportVintageSerializer()
    regions = ImportRegionSerializer(many=True, allow_empty=False)

    def validate_schema_version(self, value):
        if value != SCHEMA_VERSION:
            raise serializers.ValidationError(
                f"Unsupported schema_version '{value}'; expected {SCHEMA_VERSION}."
            )
        return value
