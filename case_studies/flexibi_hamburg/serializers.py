from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import HamburgRoadsideTrees


class HamburgRoadsideTreeGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        geo_field = 'geom'
        fields = []


class HamburgRoadsideTreeFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        fields = (
            'baumid', 'gattung_latein', 'art_latein', 'sorte_latein', 'pflanzjahr', 'kronendurchmesser', 'stammumfang',
            'strasse', 'hausnummer', 'ortsteil_nr', 'stadtteil', 'bezirk')
