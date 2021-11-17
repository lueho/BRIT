from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework.serializers import ModelSerializer
from maps.models import GeoPolygon
from . import models


class GeoreferencedWasteCollection(GeoPolygon, models.Collection):
    pass


class WasteCollectionGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoreferencedWasteCollection
        geo_field = 'geom'
        fields = ['id']


class WasteCollectionSerializer(ModelSerializer):
    class Meta:
        model = models.Collection
        fields = ['name']