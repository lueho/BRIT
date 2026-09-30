from django.db.models import Q
from rest_framework import serializers

from .models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    ScenarioInventoryConfiguration,
)


class InventoryAlgorithmParameterValueSerializer(serializers.ModelSerializer):
    """Serializer for parameter values."""

    class Meta:
        model = InventoryAlgorithmParameterValue
        fields = [
            "id",
            "name",
            "value",
            "standard_deviation",
            "source",
            "type",
            "default",
            "is_custom",
        ]


class InventoryAlgorithmParameterSerializer(serializers.ModelSerializer):
    """Serializer for algorithm parameters with nested values.

    Only curated preset values are exposed. When ``scenario_id`` is passed in
    the serializer context, custom (user-provided) values that are already
    configured in that scenario are included as well, so the configuration
    form can preselect them without leaking assumptions of other scenarios.
    """

    values = serializers.SerializerMethodField()

    def get_values(self, obj):
        values = obj.inventoryalgorithmparametervalue_set.all()
        scenario_id = self.context.get("scenario_id")
        if scenario_id:
            configured_customs = ScenarioInventoryConfiguration.objects.filter(
                scenario_id=scenario_id, inventory_parameter=obj
            ).values("inventory_value_id")
            values = values.filter(Q(is_custom=False) | Q(id__in=configured_customs))
        else:
            values = values.filter(is_custom=False)
        return InventoryAlgorithmParameterValueSerializer(
            values.order_by("id"), many=True
        ).data

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
