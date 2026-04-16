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

from .models import (
    Composition,
    Material,
    MaterialComponent,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
    WeightShare,
)


class WeightShareModelSerializer(ModelSerializer):
    component_name = StringRelatedField(source="component")
    as_percentage = ReadOnlyField()

    class Meta:
        model = WeightShare
        fields = (
            "component",
            "component_name",
            "average",
            "standard_deviation",
            "as_percentage",
        )


class CompositionModelSerializer(ModelSerializer):
    group_name = StringRelatedField(source="group")
    fractions_of_name = StringRelatedField(source="fractions_of")
    shares = SerializerMethodField()

    def get_shares(salf, obj):
        """
        Gets the weight shares of the given composition in default order but takes cares that the "Other" element
        is last in the list, regardless of the previous order.
        """
        other = MaterialComponent.objects.other()
        shares = WeightShareModelSerializer(
            obj.shares.exclude(component=other), many=True
        ).data
        other_qs = obj.shares.filter(component=other)
        if other_qs.exists():
            shares.append(
                WeightShareModelSerializer(
                    obj.shares.filter(component=other), many=True
                ).data[0]
            )
        return shares

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
        other = MaterialComponent.objects.other()
        shares = WeightShareModelSerializer(
            obj.shares.exclude(component=other), many=True
        ).data
        other_qs = obj.shares.filter(component=other)
        if other_qs.exists():
            shares.append(
                WeightShareModelSerializer(
                    obj.shares.filter(component=other), many=True
                ).data[0]
            )
        return shares

    def get_labels(self, obj):
        other = MaterialComponent.objects.other()
        labels = [share.component.name for share in obj.shares.exclude(component=other)]
        other_qs = obj.shares.filter(component=other)
        if other_qs.exists():
            labels.append("Other")
        return labels

    def get_data(self, obj):
        other = MaterialComponent.objects.other()
        data = [
            {
                "label": "Fraction",
                "unit": "%",
                "data": [
                    share.average for share in obj.shares.exclude(component=other)
                ],
            }
        ]
        other_qs = obj.shares.filter(component=other)
        if other_qs.exists():
            data[0]["data"].append(other_qs.first().average)
        return data


class MaterialPropertyValueModelSerializer(
    NumericMeasurementSerializerMixin, ModelSerializer
):
    property_name = StringRelatedField(source="property")
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
    compositions = CompositionModelSerializer(many=True)
    properties = SerializerMethodField()
    sources = SourceAbbreviationSerializer(many=True)

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


class WeightShareAPISerializer(ModelSerializer):
    component = StringRelatedField()

    class Meta:
        model = WeightShare
        fields = ("component", "average", "standard_deviation")


class CompositionAPISerializer(ModelSerializer):
    group = StringRelatedField()
    fractions_of = StringRelatedField()
    shares = WeightShareAPISerializer(many=True)

    class Meta:
        model = Composition
        fields = ("group", "fractions_of", "shares")


class SampleAPISerializer(ModelSerializer):
    timestep = StringRelatedField()
    properties = SerializerMethodField()
    compositions = CompositionAPISerializer(many=True)

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
