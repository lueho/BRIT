from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from maps.models import GeoPolygon
from maps.serializers import FieldLabelModelSerializer
from materials.models import Material
from . import models


class GeoreferencedWasteCollection(GeoPolygon, models.Collection):
    pass


class WasteCollectionGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoreferencedWasteCollection
        geo_field = 'geom'
        fields = ['id']


class OwnedObjectModelSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = ('owner', 'created_at', 'created_by', 'lastmodified_at', 'lastmodified_by', 'visible_to_groups')


class CollectorSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.Collector


class CollectionSystemSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.CollectionSystem


class WasteComponentSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = Material
        fields = ('name',)


class WasteFlyerSerializer(FieldLabelModelSerializer):
    class Meta:
        model = models.WasteFlyer
        fields = ('url',)


class WasteStreamSerializer(FieldLabelModelSerializer):
    allowed_materials = serializers.StringRelatedField(many=True, label='Allowed materials')
    category = serializers.StringRelatedField(label='Waste category')

    class Meta:
        model = models.WasteStream
        fields = ['category', 'allowed_materials']


class CollectionModelSerializer(FieldLabelModelSerializer):
    id = serializers.IntegerField(label='id')
    catchment = serializers.StringRelatedField()
    collector = serializers.StringRelatedField()
    collection_system = serializers.StringRelatedField()
    waste_category = serializers.CharField(source='waste_stream.category')
    allowed_materials = serializers.StringRelatedField(many=True, source='waste_stream.allowed_materials')
    connection_rate = serializers.SerializerMethodField()
    frequency = serializers.StringRelatedField()
    sources = serializers.StringRelatedField(source='flyers', many=True)
    comments = serializers.CharField(source='description')

    class Meta:
        model = models.Collection
        fields = ('id', 'catchment', 'collector', 'collection_system',
                  'waste_category', 'allowed_materials', 'connection_rate', 'frequency', 'sources', 'comments')

    @staticmethod
    def get_connection_rate(obj):
        if obj.connection_rate:
            value = f'{obj.connection_rate * 100}%'
            if obj.connection_rate_year:
                value += f' ({obj.connection_rate_year})'
            return value
        return None
