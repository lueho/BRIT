from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import HH_Roadside

class TreeSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HH_Roadside
        geo_field = 'geom'
        # fields = ['gattung_deutsch', 'bezirk', 'pflanzjahr', 'stammumfang']
        fields = []
        
