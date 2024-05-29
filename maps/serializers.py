from rest_framework.serializers import CharField, ModelSerializer, SerializerMethodField, IntegerField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from utils.serializers import FieldLabelModelSerializer
from .models import (Catchment, Region, LauRegion, NutsRegion, GeoPolygon, RegionAttributeTextValue, Location)


class PolygonSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoPolygon
        geo_field = 'geom'
        fields = '__all__'


class LocationModelSerializer(ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'name', 'address', 'description')


class LocationGeoFeatureModelSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = 'geom'
        fields = ('id', 'name', 'geom', 'address', 'description')


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GeoreferencedRegion(GeoPolygon, Region):
    pass


class RegionModelSerializer(ModelSerializer):
    class Meta:
        model = Region
        fields = ('id', 'name', 'country', 'description')


class RegionGeoFeatureModelSerializer(GeoFeatureModelSerializer):
    id = IntegerField(source='pk')

    class Meta:
        model = GeoreferencedRegion
        geo_field = 'geom'
        fields = ['id', 'name', 'country', 'description']


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
    level = IntegerField(source='levl_code')

    class Meta:
        model = GeoreferencedNutsRegion
        geo_field = 'geom'
        fields = ('id', 'level',)


class NutsRegionOptionSerializer(ModelSerializer):
    class Meta:
        model = NutsRegion
        fields = ['id', 'name']


class NutsRegionCatchmentOptionSerializer(ModelSerializer):
    id = SerializerMethodField()
    name = SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.region_ptr.catchment_set.first().id

    @staticmethod
    def get_name(obj):
        return obj.__str__()

    class Meta:
        model = NutsRegion
        fields = ['id', 'name']


class NutsRegionSummarySerializer(FieldLabelModelSerializer):
    name = CharField(source='name_latn')
    population = SerializerMethodField()
    population_density = SerializerMethodField()
    urban_rural_remoteness = SerializerMethodField()

    class Meta:
        model = NutsRegion
        fields = ('nuts_id', 'name', 'population', 'population_density', 'urban_rural_remoteness')

    @staticmethod
    def get_population(obj):
        qs = obj.regionattributevalue_set.filter(attribute__name='Population').order_by('-date')
        if qs.exists():
            pop = qs[0]
            return f'{int(pop.value)} ({pop.date.year})'
        else:
            return None

    @staticmethod
    def get_population_density(obj):
        qs = obj.regionattributevalue_set.filter(attribute__name='Population density').order_by('-date')
        if qs.exists():
            pd = qs[0]
            return f'{pd.value} per km² ({pd.date.year})'
        else:
            return None

    @staticmethod
    def get_urban_rural_remoteness(obj):
        try:
            return obj.regionattributetextvalue_set.get(attribute__name='Urban rural remoteness').value
        except RegionAttributeTextValue.DoesNotExist:
            return None


class LauRegionSummarySerializer(FieldLabelModelSerializer):
    name = CharField(source='lau_name')

    class Meta:
        model = LauRegion
        fields = ('lau_id', 'name')


class LauRegionOptionSerializer(ModelSerializer):
    id = SerializerMethodField()
    name = SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.region_ptr.catchment_set.first().id

    @staticmethod
    def get_name(obj):
        return obj.__str__()

    class Meta:
        model = LauRegion
        fields = ['id', 'name']


def get_nested_attr(obj, attr_path):
    """
    Fetches a nested attribute from an object given an attribute path.

    Args:
        obj (object): The object to fetch the attribute from.
        attr_path (str): The dot-separated path to the nested attribute.

    Returns:
        object: The nested attribute if found, otherwise None.
    """
    attrs = attr_path.split('.')
    for attr in attrs:
        obj = getattr(obj, attr, None)
        if obj is None:
            return None
    return obj


class BaseGeoFeatureModelSerializer(GeoFeatureModelSerializer):
    """
    Base serializer for models that include geographical data.

    This serializer dynamically fetches nested geographical attributes
    and uses a specified geometry serializer to return the geometry data
    in GeoJSON format.

    Attributes:
        geom (SerializerMethodField): Method field to fetch and serialize the geometry data.

    Methods:
        get_geom(obj):
            Fetches the nested geographical attribute using the path specified in the Meta class
            and serializes it using the specified geometry serializer.
    """
    geom = SerializerMethodField()

    def get_geom(self, obj):
        """
        Fetches the nested geographical attribute and serializes it.

        Args:
            obj (object): The object instance to fetch the geometry from.

        Returns:
            dict: The serialized GeoJSON geometry data, or None if not found.
        """
        attr_path = getattr(self.Meta, 'attr_path', '')
        geo_serializer_class = getattr(self.Meta, 'geo_serializer_class', self.__class__)
        geom_obj = get_nested_attr(obj, attr_path)
        if geom_obj and hasattr(geom_obj, 'geom'):
            return geo_serializer_class(geom_obj).data['geometry']
        return None
