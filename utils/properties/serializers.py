from rest_framework.serializers import ModelSerializer

from utils.properties.models import (
    Property,
    PropertyValue,
    Unit,
)


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
    allowed_units = UnitModelSerializer(many=True)

    class Meta:
        model = Property
        fields = ("id", "name", "allowed_units", "description")


class PropertyValueModelSerializer(ModelSerializer):
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
