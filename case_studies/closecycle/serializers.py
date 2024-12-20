from rest_framework import serializers
from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.closecycle.models import Showcase
from maps.serializers import BaseGeoFeatureModelSerializer, PolygonSerializer, RegionModelSerializer
from .models import BiogasPlantsSweden


class ShowcaseModelSerializer(ModelSerializer):
    region = RegionModelSerializer()

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description']


class ShowcaseFlatSerializer(ModelSerializer):
    region = CharField(source='region.name')

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description']


class ShowcaseSummaryListSerializer(ModelSerializer):
    """Wraps the ShowcaseModelSerializer to provide a summary of the Showcase instance.
    Returns a dictionary with an entry 'summaries', which contains a list of dictionaries, which contain the summaries
     of the respective objects."""
    summaries = ShowcaseFlatSerializer(many=True, read_only=True, source='*')

    class Meta:
        model = Showcase
        fields = ['summaries']

    def to_representation(self, data):
        if isinstance(data, list):
            return {'summaries': [ShowcaseFlatSerializer(instance).data for instance in data]}
        return {'summaries': [ShowcaseFlatSerializer(data).data]}


class ShowcaseGeoFeatureModelSerializer(BaseGeoFeatureModelSerializer):
    region = CharField(source='region.name')

    class Meta:
        model = Showcase
        geo_field = 'geom'
        attr_path = 'region.borders'
        geo_serializer_class = PolygonSerializer
        fields = ['id', 'name', 'region']


class BiogasPlantsSwedenSimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = ('id', 'type', 'county', 'creation_year', 'size', 'to_upgrade', 'main_type', 'sub_type', 'tech_type',)


class BiogasPlantsSwedenGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        geo_field = 'geom'
        fields = ('id',)


class BiogasPlantsSwedenFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = (
            'id', 'type', 'name', 'county', 'city', 'municipality', 'creation_year', 'size', 'to_upgrade', 'main_type',
            'sub_type', 'tech_type'
        )
