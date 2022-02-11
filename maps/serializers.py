from rest_framework.serializers import ModelSerializer, SerializerMethodField, IntegerField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Catchment, Region, LauRegion, NutsRegion, GeoPolygon


class PolygonSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoPolygon
        geo_field = 'geom'
        fields = '__all__'


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoreferencedRegion(GeoPolygon, Region):
    pass


class RegionSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoreferencedRegion
        geo_field = 'geom'
        fields = ['name', 'country']


class BaseResultMapSerializer(GeoFeatureModelSerializer):
    """
    This is a base class that can be used to serialize features from automatically generated tables that have their own
    models. The base initially has no model attached to it. This must me done manually before it can be instantiated.
    """

    class Meta:
        geo_field = 'geom'
        fields = '__all__'


class GeoreferencedCatchment(GeoPolygon, Catchment):
    pass


class CatchmentSerializer(GeoFeatureModelSerializer):
    level = IntegerField()

    class Meta:
        model = GeoreferencedCatchment
        geo_field = 'geom'
        fields = ['id', 'name', 'type', 'description', 'level']


class CatchmentQuerySerializer(ModelSerializer):
    class Meta:
        model = Catchment
        fields = ['owner', 'parent_region', 'type', 'name']


class GeoreferencedNutsRegion(GeoPolygon, NutsRegion):
    pass


class NutsRegionGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoreferencedNutsRegion
        geo_field = 'geom'
        fields = []


class NutsRegionOptionSerializer(ModelSerializer):
    id = SerializerMethodField()
    name = SerializerMethodField()

    def get_id(self, obj):
        return obj.region_ptr.catchment_set.first().id

    def get_name(self, obj):
        return obj.__str__()

    class Meta:
        model = NutsRegion
        fields = ['id', 'name']


class LauRegionOptionSerializer(ModelSerializer):
    id = SerializerMethodField()
    name = SerializerMethodField()

    def get_id(self, obj):
        return obj.region_ptr.catchment_set.first().id

    def get_name(self, obj):
        return obj.__str__()

    class Meta:
        model = LauRegion
        fields = ['id', 'name']
