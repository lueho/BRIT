"""Serializers implementing the versioned LAU vintage import contract."""

from rest_framework import serializers

from maps.import_common import GeometryField

from .contracts import SCHEMA_VERSION


class ImportLauVintageSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=1990, max_value=2100)
    nuts_year = serializers.IntegerField(min_value=1990, max_value=2100)


class ImportLauRegionSerializer(serializers.Serializer):
    """One LAU row of a vintage.

    Optional fields carry no defaults on purpose: an omitted field means "leave
    what BRIT holds", which a default would turn into "blank it".
    """

    cntr_code = serializers.CharField(max_length=2)
    lau_id = serializers.CharField(max_length=13)
    lau_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    name_en = serializers.CharField(max_length=113, required=False, allow_blank=True)
    # The key is required so a producer must state the parent deliberately;
    # the value may still be null for a LAU without one.
    nuts_parent_id = serializers.CharField(max_length=5, allow_null=True)
    geometry = GeometryField(required=False, allow_null=True)


class LauImportSerializer(serializers.Serializer):
    """Top-level provider-neutral import payload (``schema_version`` 1.0)."""

    schema_version = serializers.CharField()
    dry_run = serializers.BooleanField(required=False, default=False)
    vintage = ImportLauVintageSerializer()
    regions = ImportLauRegionSerializer(many=True, allow_empty=False)

    def validate_schema_version(self, value):
        if value != SCHEMA_VERSION:
            raise serializers.ValidationError(
                f"Unsupported schema_version '{value}'; expected {SCHEMA_VERSION}."
            )
        return value
