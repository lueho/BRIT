from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import HamburgRoadsideTrees


class HamburgRoadsideTreeGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HamburgRoadsideTrees
        geo_field = 'geom'
        fields = []
