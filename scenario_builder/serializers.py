from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Catchment


class BaseResultMapSerializer(GeoFeatureModelSerializer):
    """
    This is a base class that can be used to serialize features from automatically generated tables that have their own
    models. The base initially has no model attached to it. This must me done manually before it can be instantiated.
    """

    class Meta:
        geo_field = 'geom'
        fields = '__all__'


class CatchmentSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Catchment
        geo_field = 'geom'
        fields = ['title', 'type', 'description']