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


class CollectionFlatSerializer(serializers.ModelSerializer):
    catchment = serializers.StringRelatedField(label='Catchment')
    nuts_or_lau_id = serializers.StringRelatedField(source='catchment.region.nuts_or_lau_id', label='NUTS/LAU Id')
    country = serializers.StringRelatedField(source='catchment.region.country_code', label='Country')
    collector = serializers.StringRelatedField(label='Collector')
    collection_system = serializers.StringRelatedField(label='Collection System')
    waste_category = serializers.StringRelatedField(source='waste_stream.category', label='Waste Category')
    allowed_materials = serializers.SerializerMethodField(label='Allowed Materials')
    connection_rate = serializers.StringRelatedField(label='Connection Rate')
    connection_rate_year = serializers.StringRelatedField(label='Connection Rate Year')
    frequency = serializers.StringRelatedField(label='Frequency')
    comments = serializers.StringRelatedField(source='description', label='Comments')
    sources = serializers.SerializerMethodField(label='Sources')
    created_by = serializers.StringRelatedField(source='created_by.username', label='Created by')
    created_at = serializers.DateTimeField(label='Created at')
    lastmodified_by = serializers.StringRelatedField(source='lastmodified_by.username', label='Last modified by')

    class Meta:
        model = models.Collection
        fields = ('catchment', 'nuts_or_lau_id', 'country', 'collector', 'collection_system',  'waste_category',
                  'allowed_materials', 'connection_rate', 'connection_rate_year', 'frequency', 'comments', 'sources',
                  'created_by', 'created_at', 'lastmodified_by', 'lastmodified_at')

    @staticmethod
    def get_allowed_materials(obj):
        return ', '.join([m.name for m in obj.waste_stream.allowed_materials.all()])

    @staticmethod
    def get_sources(obj):
        return ', '.join([f.url for f in obj.flyers.all()])
