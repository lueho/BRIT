from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.flexibi_nantes.models import NantesGreenhouses


class NantesGreenhousesGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = NantesGreenhouses
        geo_field = 'geom'
        fields = []
