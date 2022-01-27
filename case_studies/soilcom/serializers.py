from collections import OrderedDict

from rest_framework import serializers
from rest_framework.fields import SkipField
from rest_framework.relations import PKOnlyObject
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from maps.models import GeoPolygon
from materials.models import Material
from . import models


class GeoreferencedWasteCollection(GeoPolygon, models.Collection):
    pass


class WasteCollectionGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = GeoreferencedWasteCollection
        geo_field = 'geom'
        fields = ['id']


class OwnedObjectModelSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = ('owner', 'created_at', 'created_by', 'lastmodified_at', 'lastmodified_by', 'visible_to_groups')


class CollectorSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.Collector


class CollectionSystemSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.CollectionSystem


class WasteComponentSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = Material
        fields = ('name',)


class VerboseLabelMixin(serializers.Serializer):

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
            if check_for_none is None:
                ret[field.label] = None
            else:
                ret[field.label] = field.to_representation(attribute)

        return ret


class VerboseLabelModelSerializer(VerboseLabelMixin, serializers.ModelSerializer):
    """Renders output with defined labels instead of field names"""


class WasteFlyerSerializer(VerboseLabelModelSerializer):
    class Meta:
        model = models.WasteFlyer
        fields = ('url',)


class WasteStreamSerializer(VerboseLabelModelSerializer):
    allowed_materials = serializers.StringRelatedField(many=True, label='Allowed materials')
    category = serializers.StringRelatedField(label='Waste category')

    class Meta:
        model = models.WasteStream
        fields = ['category', 'allowed_materials']


class WasteCollectionSerializer(VerboseLabelModelSerializer):
    id = serializers.IntegerField(label='id')
    catchment = serializers.StringRelatedField()
    collector = serializers.StringRelatedField()
    collection_system = serializers.StringRelatedField()
    comments = serializers.CharField(source='description')

    class Meta:
        model = models.Collection
        fields = ['id', 'catchment', 'collector', 'collection_system', 'comments']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        comments = ret.pop('Comments')
        ret.update(WasteStreamSerializer(instance.waste_stream).data)
        ret.update({'Comments': comments})
        ret.update(WasteFlyerSerializer(instance.flyer).data)
        return ret
