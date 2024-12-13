from rest_framework.serializers import ModelSerializer

from utils.properties.models import (Property, PropertyUnit, PropertyValue)


class PropertyUnitModelSerializer(ModelSerializer):
    class Meta:
        model = PropertyUnit
        fields = ('id', 'name', 'dimensionless', 'reference_quantity', 'description')


class PropertyModelSerializer(ModelSerializer):
    allowed_units = PropertyUnitModelSerializer(many=True)

    class Meta:
        model = Property
        fields = ('id', 'name', 'allowed_units', 'description')


class PropertyValueModelSerializer(ModelSerializer):
    class Meta:
        model = PropertyValue
        fields = ('id', 'property', 'unit', 'average', 'standard_deviation', 'description')
