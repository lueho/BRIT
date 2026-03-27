from rest_framework.serializers import ModelSerializer, ReadOnlyField, Serializer

from bibliography.serializers import SourceAbbreviationSerializer
from utils.properties.models import (
    Property,
    PropertyValue,
    Unit,
)


class NumericMeasurementSerializerMixin(Serializer):
    """Shared presentation fields for numeric measurements across domains."""

    average = ReadOnlyField(source="display_average")
    standard_deviation = ReadOnlyField(source="display_standard_deviation")
    unit = ReadOnlyField(source="measurement_unit_label")
    sources = SourceAbbreviationSerializer(many=True, read_only=True)


class UnitModelSerializer(ModelSerializer):
    class Meta:
        model = Unit
        fields = (
            "id",
            "name",
            "symbol",
            "dimensionless",
            "reference_quantity",
            "description",
        )


class PropertyModelSerializer(ModelSerializer):
    """Serializer for the generic ``utils.properties.Property`` table."""

    allowed_units = UnitModelSerializer(many=True)

    class Meta:
        model = Property
        fields = ("id", "name", "allowed_units", "description")


class PropertyValueModelSerializer(NumericMeasurementSerializerMixin, ModelSerializer):
    """Serializer for ``PropertyValue``-style records that still use generic ``Property``."""

    class Meta:
        model = PropertyValue
        fields = (
            "id",
            "property",
            "unit",
            "average",
            "standard_deviation",
            "description",
        )
