from rest_framework_gis.serializers import GeoFeatureModelSerializer

from gis_source_manager.models import HamburgRoadsideTrees, NantesGreenhouses


class HamburgRoadsideTreeGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        geo_field = 'geom'
        fields = []


class NantesGreenhousesGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = NantesGreenhouses
        geo_field = 'geom'
        fields = []
