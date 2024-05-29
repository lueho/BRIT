from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer

from case_studies.closecycle.models import Showcase
from maps.serializers import PolygonSerializer, BaseGeoFeatureModelSerializer, RegionModelSerializer
from utils.serializers import FieldLabelModelSerializer


class ShowcaseModelSerializer(ModelSerializer):
    region = RegionModelSerializer()

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description']


class ShowcaseFlatSerializer(ModelSerializer):
    region = CharField(source='region.name', label='Tha REGION')

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description']


class ShowcaseSummaryListSerializer(ModelSerializer):
    """Wraps the ShowcaseModelSerializer to provide a summary of the Showcase instance.
    Returns a dictionary with an entry 'summaries', which contains a list of dictionaries, which contain the summaries
     of the respective objects."""
    summaries = ShowcaseFlatSerializer(many=True, read_only=True, source='*')

    class Meta:
        model = Showcase
        fields = ['summaries']

    def to_representation(self, data):
        if isinstance(data, list):
            return {'summaries': [ShowcaseFlatSerializer(instance).data for instance in data]}
        return {'summaries': [ShowcaseFlatSerializer(data).data]}


class ShowcaseGeoFeatureModelSerializer(BaseGeoFeatureModelSerializer):
    class Meta:
        model = Showcase
        geo_field = 'geom'
        attr_path = 'region.borders'
        geo_serializer_class = PolygonSerializer
        fields = ['id', 'name', 'description']
