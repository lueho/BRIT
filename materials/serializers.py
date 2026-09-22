from rest_framework.fields import Field
from rest_framework.serializers import (
    HyperlinkedRelatedField,
    ModelSerializer,
    PrimaryKeyRelatedField,
    ReadOnlyField,
    Serializer,
    SerializerMethodField,
    StringRelatedField,
    ValidationError,
)

from bibliography.models import Source
from bibliography.serializers import SourceAbbreviationSerializer
from distributions.models import TemporalDistribution
from utils.object_management.permissions import filter_queryset_for_user
from utils.properties.serializers import NumericMeasurementSerializerMixin

from .composition_normalization import get_sample_normalized_compositions
from .models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialPropertyValue,
    Sample,
    SampleGroup,
    SampleSeries,
)


def _get_composition_shares(composition):
    """Normalized shares belonging to a single ``Composition`` settings row."""
    for normalized in get_sample_normalized_compositions(composition.sample):
        if normalized.get("settings_pk") == composition.pk:
            return normalized["shares"]
    return []


def _visible_related(queryset, context):
    """Related objects the request user may see; published-only without one."""
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None:
        return queryset.filter(publication_status="published")
    return filter_queryset_for_user(queryset, user)


class NormalizedCompositionsField(Field):
    """Read-only field rendering a sample's normalized compositions."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        return get_sample_normalized_compositions(instance)


class CompositionModelSerializer(ModelSerializer):
    group_name = ReadOnlyField(source="group.name")
    fractions_of_name = ReadOnlyField(source="fractions_of.name")
    shares = SerializerMethodField()

    def get_shares(self, obj):
        return _get_composition_shares(obj)

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

    def get_labels(self, obj):
        return [share["component_name"] for share in _get_composition_shares(obj)]

    def get_data(self, obj):
        return [
            {
                "label": "Fraction",
                "unit": "%",
                "data": [share["average"] for share in _get_composition_shares(obj)],
            }
        ]


MEASUREMENT_METADATA_FIELDS = (
    "display_value",
    "value_qualifier",
    "raw_value",
    "detection_limit",
    "raw_detection_limit",
)


class MeasurementMetadataSerializerMixin(Serializer):
    display_value = ReadOnlyField()
    value_qualifier = ReadOnlyField()
    raw_value = ReadOnlyField()
    detection_limit = ReadOnlyField()
    raw_detection_limit = ReadOnlyField()


class MaterialPropertyValueModelSerializer(
    MeasurementMetadataSerializerMixin,
    NumericMeasurementSerializerMixin,
    ModelSerializer,
):
    property_name = ReadOnlyField(source="property.name")
    property_url = HyperlinkedRelatedField(
        source="property", read_only=True, view_name="materialproperty-detail-modal"
    )
    basis_component = ReadOnlyField(source="basis_component.name")
    analytical_method = StringRelatedField()
    sources = SourceAbbreviationSerializer(many=True, read_only=True)

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
        ) + MEASUREMENT_METADATA_FIELDS


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
    compositions = NormalizedCompositionsField()
    properties = SerializerMethodField()
    sources = SourceAbbreviationSerializer(many=True)

    def get_properties(self, obj):
        request = self.context.get("request")
        queryset = (
            obj.get_property_values_queryset()
            .select_related(
                "property",
                "basis_component",
                "analytical_method",
                "unit",
            )
            .prefetch_related("sources")
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
            "datetime_precision",
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
            "datetime_precision",
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


class BaseMaterialPropertyAPISerializer(
    MeasurementMetadataSerializerMixin, ModelSerializer
):
    name = StringRelatedField(source="property")
    basis_component = ReadOnlyField(source="basis_component.name")

    class Meta:
        model = MaterialPropertyValue
        fields = (
            "name",
            "basis_component",
            "unit",
            "average",
            "standard_deviation",
        ) + MEASUREMENT_METADATA_FIELDS


class MaterialPropertyAPISerializer(
    NumericMeasurementSerializerMixin, BaseMaterialPropertyAPISerializer
):
    pass


class CompositionAPISerializer(ModelSerializer):
    group = StringRelatedField()
    fractions_of = StringRelatedField()
    shares = SerializerMethodField()

    def get_shares(self, obj):
        return [
            {
                "component": share["component_name"],
                "average": share["average"],
                "standard_deviation": share["standard_deviation"],
            }
            for share in _get_composition_shares(obj)
        ]

    class Meta:
        model = Composition
        fields = ("group", "fractions_of", "shares")


class SampleGroupSummarySerializer(ModelSerializer):
    """Compact group representation embedded in sample payloads."""

    class Meta:
        model = SampleGroup
        fields = ("id", "name", "kind")


class SampleAPISerializer(ModelSerializer):
    timestep = StringRelatedField()
    compositions = NormalizedCompositionsField()
    properties = SerializerMethodField()
    sample_groups = SerializerMethodField()

    def get_sample_groups(self, obj):
        queryset = _visible_related(obj.sample_groups.all(), self.context)
        return SampleGroupSummarySerializer(queryset, many=True).data

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
        fields = ("name", "timestep", "properties", "compositions", "sample_groups")


class SampleSeriesAPISerializer(ModelSerializer):
    material = MaterialAPISerializer()
    samples = SampleAPISerializer(many=True)

    class Meta:
        model = SampleSeries
        fields = ("material", "samples")


class SampleGroupMemberSerializer(ModelSerializer):
    material = StringRelatedField()
    timestep = StringRelatedField()

    class Meta:
        model = Sample
        fields = ("id", "name", "material", "timestep")


class SampleGroupAPISerializer(ModelSerializer):
    sources = SerializerMethodField()
    samples = SerializerMethodField()

    def get_sources(self, obj):
        queryset = _visible_related(obj.sources.all(), self.context)
        return SourceAbbreviationSerializer(queryset, many=True).data

    def get_samples(self, obj):
        queryset = _visible_related(obj.samples.all(), self.context)
        return SampleGroupMemberSerializer(queryset, many=True).data

    class Meta:
        model = SampleGroup
        fields = ("id", "name", "kind", "description", "sources", "samples")


# ----------- Write (mutation) serializers -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialWriteSerializer(ModelSerializer):
    class Meta:
        model = Material
        fields = (
            "id",
            "name",
            "abbreviation",
            "categories",
            "description",
        )


class SampleSeriesWriteSerializer(ModelSerializer):
    class Meta:
        model = SampleSeries
        fields = (
            "id",
            "name",
            "material",
            "description",
            "image",
            "publish",
            "standard",
        )


class SampleGroupWriteSerializer(ModelSerializer):
    sources = PrimaryKeyRelatedField(
        many=True,
        queryset=Source.objects.all(),
        required=False,
    )
    samples = PrimaryKeyRelatedField(
        many=True,
        queryset=Sample.objects.all(),
        required=False,
    )

    def validate_sources(self, value):
        return self._validate_visible(value, Source)

    def validate_samples(self, value):
        return self._validate_visible(value, Sample)

    def _validate_visible(self, value, model):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            if value:
                raise ValidationError(
                    "Authentication is required to assign related objects."
                )
            return value
        visible = filter_queryset_for_user(model.objects.all(), user)
        if any(not visible.filter(pk=item.pk).exists() for item in value):
            raise ValidationError("One or more selected objects are not accessible.")
        return value

    class Meta:
        model = SampleGroup
        fields = (
            "id",
            "name",
            "kind",
            "description",
            "sources",
            "samples",
        )


class SampleWriteSerializer(ModelSerializer):
    # sources is a M2M field without blank=True on the model; make it optional
    # in the API so callers can add sources later.
    sources = PrimaryKeyRelatedField(
        many=True,
        queryset=Source.objects.all(),
        required=False,
    )
    sample_groups = PrimaryKeyRelatedField(
        many=True,
        queryset=SampleGroup.objects.all(),
        required=False,
    )

    def validate_sample_groups(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            if value:
                raise ValidationError(
                    "Authentication is required to assign sample groups."
                )
            return value
        if user.is_staff:
            editable = SampleGroup.objects.all()
        else:
            editable = SampleGroup.objects.editable_by_user(user)
        if any(not editable.filter(pk=group.pk).exists() for group in value):
            raise ValidationError(
                "One or more selected sample groups cannot be edited."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        precision = attrs.get(
            "datetime_precision", getattr(self.instance, "datetime_precision", "")
        )
        sampling_datetime = attrs.get(
            "datetime", getattr(self.instance, "datetime", None)
        )
        if precision and sampling_datetime is None:
            raise ValidationError(
                {
                    "datetime_precision": "Sampling date is required when precision is set."
                }
            )
        return attrs

    class Meta:
        model = Sample
        fields = (
            "id",
            "name",
            "material",
            "series",
            "standalone",
            "timestep",
            "sample_groups",
            "datetime",
            "datetime_precision",
            "location",
            "analysis_date",
            "analysis_laboratory",
            "lab_accreditation",
            "analysis_objective",
            "sources",
            "description",
            "image",
        )


class CompositionWriteSerializer(ModelSerializer):
    class Meta:
        model = Composition
        fields = (
            "id",
            "sample",
            "group",
            "fractions_of",
            "order",
        )


class ComponentMeasurementReadSerializer(
    MeasurementMetadataSerializerMixin, ModelSerializer
):
    component = StringRelatedField()
    group = StringRelatedField()
    basis_component = StringRelatedField()
    analytical_method = StringRelatedField()
    unit = StringRelatedField()
    sources = SourceAbbreviationSerializer(many=True, read_only=True)

    class Meta:
        model = ComponentMeasurement
        fields = (
            "id",
            "sample",
            "group",
            "component",
            "basis_component",
            "analytical_method",
            "sources",
            "unit",
            "average",
            "standard_deviation",
            "sample_size",
            "comment",
        ) + MEASUREMENT_METADATA_FIELDS


class ComponentMeasurementWriteSerializer(ModelSerializer):
    class Meta:
        model = ComponentMeasurement
        fields = (
            "id",
            "sample",
            "group",
            "component",
            "basis_component",
            "analytical_method",
            "sources",
            "unit",
            "average",
            "standard_deviation",
            "sample_size",
            "comment",
        )

    def validate_unit(self, unit):
        if not unit.is_weight_fraction:
            raise ValidationError(
                "Component measurements must use a weight-fraction unit "
                "(e.g. %, g/kg, mg/kg)."
            )
        return unit


class MaterialPropertyValueReadSerializer(
    MeasurementMetadataSerializerMixin, ModelSerializer
):
    property = StringRelatedField()
    basis_component = StringRelatedField()
    analytical_method = StringRelatedField()
    unit = StringRelatedField()
    sources = SourceAbbreviationSerializer(many=True, read_only=True)

    class Meta:
        model = MaterialPropertyValue
        fields = (
            "id",
            "sample",
            "property",
            "basis_component",
            "analytical_method",
            "sources",
            "unit",
            "average",
            "standard_deviation",
        ) + MEASUREMENT_METADATA_FIELDS


class MaterialPropertyValueWriteSerializer(ModelSerializer):
    class Meta:
        model = MaterialPropertyValue
        fields = (
            "id",
            "sample",
            "property",
            "basis_component",
            "analytical_method",
            "sources",
            "unit",
            "average",
            "standard_deviation",
        )
