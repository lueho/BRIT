from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer
import rest_framework_gis as rf

from .models import Catchment, Region, NutsRegion, GeoPolygon
from django.db import models
from brit.models import NamedUserObjectModel
from django.contrib.gis.db.models import MultiPolygonField, PointField


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
    class Meta:
        model = Catchment
        geo_field = 'geom'
        fields = ['name', 'type', 'description']


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
