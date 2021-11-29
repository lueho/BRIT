from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField
from django.utils.text import capfirst

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


class VerboseFieldLabelsMixin(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'labels' in self.fields:
            raise RuntimeError(
                'You cant have labels field defined '
                'while using MyModelSerializer'
            )

        self.fields['labels'] = SerializerMethodField()

    def get_labels(self, *args):
        labels = {}

        for field in self.Meta.model._meta.get_fields():
            if field.name in self.fields:
                labels[field.name] = capfirst(field.verbose_name)
        return labels

    @property
    def verbose_data(self):

        ret = super().data
        labels = ret.pop('labels')
        return {labels[key] if key in labels else key: value for key, value in ret.items()}


class WasteFlyerSerializer(VerboseFieldLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = models.WasteFlyer
        fields = ('url',)


class WasteStreamSerializer(VerboseFieldLabelsMixin, serializers.ModelSerializer):
    allowed_materials = serializers.StringRelatedField(many=True)
    category = serializers.StringRelatedField(label='Waste category')

    class Meta:
        model = models.WasteStream
        fields = ['category', 'allowed_materials']


class WasteCollectionSerializer(VerboseFieldLabelsMixin, serializers.ModelSerializer):
    collector = serializers.StringRelatedField()
    collection_system = serializers.StringRelatedField()
    comments = serializers.CharField(source='description')

    class Meta:
        model = models.Collection
        fields = ['name', 'collector', 'collection_system', 'comments']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        comments = ret.pop('comments')
        ret.update(WasteStreamSerializer(instance.waste_stream).verbose_data)
        ret.update({'Comments': comments})
        ret.update(WasteFlyerSerializer(instance.flyer).data)
        return ret
