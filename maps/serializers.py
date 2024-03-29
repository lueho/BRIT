from collections import OrderedDict

from rest_framework.fields import SkipField
from rest_framework.relations import PKOnlyObject
from rest_framework.serializers import CharField, ModelSerializer, SerializerMethodField, IntegerField, Serializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import (Catchment, Region, LauRegion, NutsRegion, GeoPolygon, RegionAttributeTextValue, Location)


class FieldLabelMixin(Serializer):
    field_labels_as_keys = False

    def __init__(self, *args, **kwargs):
        self.field_labels_as_keys = kwargs.pop('field_labels_as_keys', self.field_labels_as_keys)
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):

        ret = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            # We skip `to_representation` for `None` values so that fields do
            # not have to explicitly deal with that case.
            #
            # For related fields with `use_pk_only_optimization` we need to
            # resolve the pk value.
            check_for_none = attribute.pk if isinstance(attribute, PKOnlyObject) else attribute
            key = field.label if self.field_labels_as_keys else field.field_name
            if check_for_none is None:
                ret[key] = None
            else:
                ret[key] = field.to_representation(attribute)

        return ret


class FieldLabelModelSerializer(FieldLabelMixin, ModelSerializer):
    """Renders output with defined labels instead of field names"""


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
