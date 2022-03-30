from rest_framework.serializers import PrimaryKeyRelatedField, ReadOnlyField, StringRelatedField, \
    HyperlinkedRelatedField, ModelSerializer, SerializerMethodField

from bibliography.serializers import SourceAbbreviationSerializer
from distributions.models import TemporalDistribution
from .models import Composition, MaterialPropertyValue, Sample, WeightShare, SampleSeries, MaterialComponent


class WeightShareModelSerializer(ModelSerializer):
    component_name = StringRelatedField(source='component')
    as_percentage = ReadOnlyField()

    class Meta:
        model = WeightShare
        fields = ('component', 'component_name', 'average', 'standard_deviation', 'as_percentage')


class CompositionModelSerializer(ModelSerializer):
    group_name = StringRelatedField(source='group')
    fractions_of_name = StringRelatedField(source='fractions_of')
    shares = SerializerMethodField()

    def get_shares(self, obj):
        """
        Gets the weight shares of the given composition in default order but takes cares that the "Other" element
        is last in the list, regardless of the previous order.
        """
        other = MaterialComponent.objects.other()
        shares = WeightShareModelSerializer(obj.shares.exclude(component=other), many=True).data
        other_qs = obj.shares.filter(component=other)
        if other_qs.exists():
            shares.append(WeightShareModelSerializer(obj.shares.filter(component=other), many=True).data[0])
        return shares

    class Meta:
        model = Composition
        fields = ('id', 'group', 'group_name', 'sample', 'fractions_of', 'fractions_of_name', 'shares',)


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
