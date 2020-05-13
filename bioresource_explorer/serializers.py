from rest_framework_gis.serializers import GeoFeatureModelSerializer

from gis_source_manager.models import HamburgRoadsideTrees


class HamburgRoadsideTreeGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        geo_field = 'geom'
        fields = []
