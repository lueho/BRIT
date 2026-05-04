from rest_framework.serializers import (
    HyperlinkedRelatedField,
    ModelSerializer,
    ReadOnlyField,
    SerializerMethodField,
    StringRelatedField,
)

from bibliography.serializers import SourceAbbreviationSerializer
from distributions.models import TemporalDistribution
from utils.properties.serializers import NumericMeasurementSerializerMixin

from .composition_normalization import get_sample_normalized_compositions
from .models import (
    Composition,
    Material,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
)


class CompositionModelSerializer(ModelSerializer):
    group_name = ReadOnlyField(source="group.name")
    fractions_of_name = ReadOnlyField(source="fractions_of.name")
    shares = SerializerMethodField()

    def get_shares(self, obj):
        for composition in get_sample_normalized_compositions(obj.sample):
            if composition.get("settings_pk") == obj.pk:
                return composition["shares"]
        return []

    class Meta:
        model = Composition
        fields = (
            "id",
            "group",
            "group_name",
            "sample",
            "fractions_of",
            "fractions_of_name",
            "shares",
        )


class CompositionDoughnutChartSerializer(ModelSerializer):
    id = SerializerMethodField()
    title = ReadOnlyField(default="Composition")
    unit = ReadOnlyField(default="%")
    labels = SerializerMethodField()
    data = SerializerMethodField()

    class Meta:
        model = Composition
        fields = ("id", "title", "unit", "labels", "data")

    def get_id(self, obj):
        return f"materialCompositionChart-{obj.id}"

    def get_shares(self, obj):
        for composition in get_sample_normalized_compositions(obj.sample):
            if composition.get("settings_pk") == obj.pk:
                return composition["shares"]
        return []

    def get_labels(self, obj):
        return [share["component_name"] for share in self.get_shares(obj)]

    def get_data(self, obj):
        return [
            {
                "label": "Fraction",
                "unit": "%",
                "data": [share["average"] for share in self.get_shares(obj)],
            }
        ]


class MaterialPropertyValueModelSerializer(
    NumericMeasurementSerializerMixin, ModelSerializer
):
    property_name = ReadOnlyField(source="property.name")
    property_url = HyperlinkedRelatedField(
        source="property", read_only=True, view_name="materialproperty-detail-modal"
    )
    basis_component = ReadOnlyField(source="basis_component.name")
    analytical_method = StringRelatedField()

    class Meta:
        model = MaterialPropertyValue
        fields = (
            "id",
            "property",
            "property_name",
            "property_url",
            "basis_component",
            "analytical_method",
            "sources",
            "average",
            "standard_deviation",
            "unit",
        )


class SampleTimestepsSerializer(ModelSerializer):
    timestep = StringRelatedField(source="timestep.name")

    class Meta:
        model = Sample
        fields = ("id", "timestep")


class SamplesPerTemporalDistributionSerializer(ModelSerializer):
    samples = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.series = kwargs.pop("series")
        super().__init__(*args, **kwargs)

    def get_samples(self, obj):
        queryset = Sample.objects.filter(series=self.series, timestep__distribution=obj)
        serializer = SampleTimestepsSerializer(queryset, many=True)
        return serializer.data

    class Meta:
        model = TemporalDistribution
        fields = ("id", "name", "description", "samples")


class SampleSeriesModelSerializer(ModelSerializer):
    distributions = SerializerMethodField()

    def get_distributions(self, obj):
        distributions = obj.temporal_distributions.all()
        serializer = SamplesPerTemporalDistributionSerializer(
            distributions, many=True, series=self.instance
        )
        return serializer.data

    class Meta:
        model = SampleSeries
        fields = ("id", "name", "description", "distributions")


class SampleModelSerializer(ModelSerializer):
    material_name = StringRelatedField(source="material")
    material_url = HyperlinkedRelatedField(
        source="material", read_only=True, view_name="material-detail"
    )
    timestep = StringRelatedField()
    series_name = StringRelatedField(source="series")
    series_url = HyperlinkedRelatedField(
        source="series", read_only=True, view_name="sampleseries-detail"
    )
    compositions = SerializerMethodField()
    properties = SerializerMethodField()
    sources = SourceAbbreviationSerializer(many=True)

    def get_compositions(self, obj):
        return get_sample_normalized_compositions(obj)

    def get_properties(self, obj):
        request = self.context.get("request")
        queryset = obj.get_property_values_queryset().select_related(
            "property",
            "basis_component",
            "analytical_method",
            "unit",
        )
        return MaterialPropertyValueModelSerializer(
            queryset.order_by("property__name", "id"),
            many=True,
            context={"request": request},
        ).data

    class Meta:
        model = Sample
        fields = (
            "name",
            "material",
            "material_name",
            "material_url",
            "series",
            "series_name",
            "series_url",
            "timestep",
            "datetime",
            "image",
            "compositions",
            "properties",
            "sources",
            "description",
        )


class SampleFlatSerializer(ModelSerializer):
    material = StringRelatedField()
    series = StringRelatedField()
    timestep = StringRelatedField()
    owner = StringRelatedField()
    detail_url = SerializerMethodField()

    class Meta:
        model = Sample
        fields = (
            "id",
            "name",
            "material",
            "series",
            "timestep",
            "datetime",
            "standalone",
            "publication_status",
            "owner",
            "created_at",
            "description",
            "detail_url",
        )

    def get_detail_url(self, obj):
        return obj.get_absolute_url()


# ----------- API ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialAPISerializer(ModelSerializer):
    categories = StringRelatedField(many=True)

    class Meta:
        model = Material
        fields = ("name", "categories")


class BaseMaterialPropertyAPISerializer(ModelSerializer):
    name = StringRelatedField(source="property")
    basis_component = ReadOnlyField(source="basis_component.name")

    class Meta:
        model = MaterialPropertyValue
        fields = ("name", "basis_component", "unit", "average", "standard_deviation")


class MaterialPropertyAPISerializer(
    NumericMeasurementSerializerMixin, BaseMaterialPropertyAPISerializer
):
    pass


class CompositionAPISerializer(ModelSerializer):
    group = StringRelatedField()
    fractions_of = StringRelatedField()
    shares = SerializerMethodField()

    def get_shares(self, obj):
        for composition in get_sample_normalized_compositions(obj.sample):
            if composition.get("settings_pk") != obj.pk:
                continue
            return [
                {
                    "component": share["component_name"],
                    "average": share["average"],
                    "standard_deviation": share["standard_deviation"],
                }
                for share in composition["shares"]
            ]
        return []

    class Meta:
        model = Composition
        fields = ("group", "fractions_of", "shares")


class SampleAPISerializer(ModelSerializer):
    timestep = StringRelatedField()
    properties = SerializerMethodField()
    compositions = SerializerMethodField()

    def get_compositions(self, obj):
        return get_sample_normalized_compositions(obj)

    def get_properties(self, obj):
        queryset = obj.get_property_values_queryset().select_related(
            "property",
            "basis_component",
            "unit",
        )
        return MaterialPropertyAPISerializer(
            queryset.order_by("property__name", "id"), many=True
        ).data

    class Meta:
        model = Sample
        fields = ("name", "timestep", "properties", "compositions")


class SampleSeriesAPISerializer(ModelSerializer):
    material = MaterialAPISerializer()
    samples = SampleAPISerializer(many=True)

    class Meta:
        model = SampleSeries
        fields = ("material", "samples")
