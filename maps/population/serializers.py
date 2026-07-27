"""Serializers implementing the versioned population bulk-import contract."""

from rest_framework import serializers

from .contracts import SCHEMA_VERSION, SUPPORTED_INDICATORS, UNIT_TO_PERSONS
from .models import GeographicScope, SourceStatus, TemporalBasis


class ImportDatasetSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=100)
    name = serializers.CharField(max_length=255)
    provider = serializers.CharField(max_length=255)
    external_id = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    release = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    geographic_scope = serializers.ChoiceField(choices=GeographicScope.choices)
    temporal_basis = serializers.ChoiceField(choices=TemporalBasis.choices)
    source_unit = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default=""
    )
    classification_version = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default=""
    )
    is_canonical = serializers.BooleanField(required=False, default=False)


class ImportObservationSerializer(serializers.Serializer):
    region_scheme = serializers.ChoiceField(choices=["NUTS", "LAU"])
    region_code = serializers.CharField(max_length=50)
    region_version = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default=""
    )
    indicator = serializers.ChoiceField(choices=list(SUPPORTED_INDICATORS))
    reference_period = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=20, decimal_places=6)
    unit = serializers.ChoiceField(choices=sorted(UNIT_TO_PERSONS))
    source_status = serializers.ChoiceField(
        choices=SourceStatus.choices, required=False, default=SourceStatus.FINAL
    )
    flags = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )


class PopulationImportSerializer(serializers.Serializer):
    """Top-level provider-neutral import payload (``schema_version`` 1.0)."""

    schema_version = serializers.CharField()
    dry_run = serializers.BooleanField(required=False, default=False)
    extracted_at = serializers.DateTimeField(required=False, allow_null=True)
    upstream_updated_at = serializers.DateTimeField(required=False, allow_null=True)
    checksum = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    dataset = ImportDatasetSerializer()
    observations = ImportObservationSerializer(many=True, allow_empty=False)

    def validate_schema_version(self, value):
        if value != SCHEMA_VERSION:
            raise serializers.ValidationError(
                f"Unsupported schema_version '{value}'. Expected '{SCHEMA_VERSION}'."
            )
        return value
