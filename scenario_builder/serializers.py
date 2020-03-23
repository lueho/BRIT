from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import Catchment

class CatchmentSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Catchment
        geo_field = 'geom'
        fields = ['title', 'type', 'description']