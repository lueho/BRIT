from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import HamburgRoadsideTrees


class HamburgRoadsideTreeSimpleModelSerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()

    class Meta:
        model = HamburgRoadsideTrees
        fields = ('id', 'art_latein', 'pflanzjahr', 'kronendurchmesser', 'stammumfang', 'address')

    @staticmethod
    def get_address(obj):
        return f"{obj.strasse}{' ' + obj.hausnummer if obj.hausnummer is not None and obj.hausnummer != '0' else ''}"


class HamburgRoadsideTreeGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        geo_field = 'geom'
        fields = ('id',)


class HamburgRoadsideTreeFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        fields = (
            'baumid', 'gattung_latein', 'art_latein', 'sorte_latein', 'pflanzjahr', 'kronendurchmesser', 'stammumfang',
            'strasse', 'hausnummer', 'ortsteil_nr', 'stadtteil', 'bezirk')
