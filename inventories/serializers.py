from rest_framework import serializers

from .models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
)


class InventoryAlgorithmParameterValueSerializer(serializers.ModelSerializer):
    """Serializer for parameter values."""

    class Meta:
        model = InventoryAlgorithmParameterValue
        fields = ["id", "name", "value", "default"]


class InventoryAlgorithmParameterSerializer(serializers.ModelSerializer):
    """Serializer for algorithm parameters with nested values."""

    values = InventoryAlgorithmParameterValueSerializer(
        source="inventoryalgorithmparametervalue_set", many=True, read_only=True
    )

    class Meta:
        model = InventoryAlgorithmParameter
        fields = [
            "id",
            "descriptive_name",
            "short_name",
            "unit",
            "is_required",
            "values",
        ]


class InventoryAlgorithmSerializer(serializers.ModelSerializer):
    """Basic serializer for inventory algorithms."""

    class Meta:
        model = InventoryAlgorithm
        fields = ["id", "name", "description"]
