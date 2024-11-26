from rest_framework_gis.serializers import GeoFeatureModelSerializer, ModelSerializer

from .models import NantesGreenhouses


class NantesGreenhousesModelSerializer(ModelSerializer):
    class Meta:
        model = NantesGreenhouses
        fields = ('nb_cycles', 'culture_1', 'culture_2', 'culture_3', 'heated', 'lighted', 'high_wire', 'above_ground',
                  'surface_ha')


class NantesGreenhousesFlatSerializer(ModelSerializer):
    class Meta:
        model = NantesGreenhouses
        fields = ('nb_cycles', 'culture_1', 'culture_2', 'culture_3', 'heated', 'lighted', 'high_wire', 'above_ground',
                  'surface_ha')


class NantesGreenhousesGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = NantesGreenhouses
        geo_field = 'geom'
        fields = []
