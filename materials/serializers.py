from rest_framework.serializers import PrimaryKeyRelatedField, ReadOnlyField, StringRelatedField, \
    HyperlinkedRelatedField, ModelSerializer, SerializerMethodField

from bibliography.serializers import SourceAbbreviationSerializer
from distributions.models import TemporalDistribution
from .models import Composition, MaterialPropertyValue, Sample, WeightShare, SampleSeries


class WeightShareModelSerializer(ModelSerializer):
    component_name = StringRelatedField(source='component')
    component_url = HyperlinkedRelatedField(source='component', read_only=True,
                                            view_name='materialcomponent-detail-modal')
    as_percentage = ReadOnlyField()

    class Meta:
        model = WeightShare
        fields = ('component', 'component_name', 'component_url', 'average', 'standard_deviation', 'as_percentage')


class CompositionModelSerializer(ModelSerializer):
    group_name = StringRelatedField(source='group')
    group_url = HyperlinkedRelatedField(source='group', read_only=True, view_name='materialcomponentgroup-detail-modal')
    fractions_of_name = StringRelatedField(source='fractions_of')
    fractions_of_url = HyperlinkedRelatedField(
        source='fractions_of',
        read_only=True,
        view_name='materialcomponent-detail'
    )
    shares = WeightShareModelSerializer(many=True)

    class Meta:
        model = Composition
        fields = (
        'id', 'group', 'group_url', 'group_name', 'sample', 'fractions_of', 'fractions_of_name', 'fractions_of_url',
        'shares')


class MaterialPropertyValueModelSerializer(ModelSerializer):
    property_name = StringRelatedField(source='property')
    property_url = HyperlinkedRelatedField(source='property', read_only=True, view_name='materialproperty-detail-modal')
    unit = StringRelatedField(source='property.unit')

    class Meta:
        model = MaterialPropertyValue
        fields = ('id', 'property', 'property_name', 'property_url', 'average', 'standard_deviation', 'unit')


class SampleTimestepsSerializer(ModelSerializer):
    timestep = StringRelatedField(source='timestep.name')

    class Meta:
        model = Sample
        fields = ('id', 'timestep')


class SamplesPerTemporalDistributionSerializer(ModelSerializer):
    samples = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.series = kwargs.pop('series')
        super().__init__(*args, **kwargs)

    def get_samples(self, obj):
        queryset = Sample.objects.filter(series=self.series, timestep__distribution=obj)
        serializer = SampleTimestepsSerializer(queryset, many=True)
        return serializer.data

    class Meta:
        model = TemporalDistribution
        fields = ('id', 'name', 'description', 'samples')


class SampleSeriesModelSerializer(ModelSerializer):
    distributions = SerializerMethodField()

    def get_distributions(self, obj):
        distributions = obj.temporal_distributions.all()
        serializer = SamplesPerTemporalDistributionSerializer(distributions, many=True, series=self.instance)
        return serializer.data

    class Meta:
        model = SampleSeries
        fields = ('id', 'name', 'description', 'distributions')


class SampleModelSerializer(ModelSerializer):
    material = PrimaryKeyRelatedField(source='series.material', read_only=True)
    material_name = StringRelatedField(source='series.material')
    material_url = HyperlinkedRelatedField(source='series.material', read_only=True, view_name='material-detail-modal')
    timestep = StringRelatedField()
    series_name = StringRelatedField(source='series')
    series_url = HyperlinkedRelatedField(source='series', read_only=True, view_name='sampleseries-detail-modal')
    compositions = CompositionModelSerializer(many=True)
    properties = MaterialPropertyValueModelSerializer(many=True)
    sources = SourceAbbreviationSerializer(many=True)

    class Meta:
        model = Sample
        fields = (
            'name', 'material', 'material_name', 'material_url', 'series', 'series_name', 'series_url', 'timestep',
            'taken_at', 'preview',
            'compositions', 'properties', 'sources')
