from collections import OrderedDict

from rest_framework import serializers
from rest_framework_gis.fields import GeometrySerializerMethodField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from maps.models import GeoPolygon
from materials.models import Material
from utils.object_management.permissions import get_object_policy
from utils.properties.models import Property
from utils.serializers import FieldLabelModelSerializer

from . import models

# Geometry simplification tolerance in degrees (approx 100m at equator)
# Lower values = more detail, higher values = more simplification
GEOMETRY_SIMPLIFY_TOLERANCE = 0.001


class GeoreferencedWasteCollection(GeoPolygon, models.Collection):
    pass


class GeoreferencedCollector(GeoPolygon, models.Collector):
    """Proxy model combining Collector with GeoPolygon for GeoJSON serialization."""

    pass


class WasteCollectionGeometrySerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for waste collections with simplified geometry.

    Uses simplified geometry to reduce payload size and improve performance.
    The geometry is simplified using ST_SimplifyPreserveTopology to maintain
    valid topology while reducing point count.
    """

    catchment = serializers.StringRelatedField(source="catchment.name")
    waste_category = serializers.StringRelatedField(source="waste_stream.category.name")
    collection_system = serializers.StringRelatedField(source="collection_system.name")
    geom = GeometrySerializerMethodField()

    class Meta:
        model = GeoreferencedWasteCollection
        geo_field = "geom"
        fields = ["id", "catchment", "waste_category", "collection_system"]

    def get_geom(self, instance):
        """Return simplified geometry if available, otherwise original.

        The simplified_geom annotation is added by the viewset queryset.
        Falls back to original geometry if annotation is not present.
        """
        # Check for pre-simplified geometry annotation
        if hasattr(instance, "simplified_geom") and instance.simplified_geom:
            return instance.simplified_geom
        # Fall back to original geometry
        return getattr(instance, "geom", None)


class CollectorGeometrySerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for Collectors with geometry and organizational level.
    Used by QGIS for map rendering.
    """

    collector = serializers.CharField(source="name", read_only=True)
    catchment = serializers.SerializerMethodField()
    orga_level = serializers.SerializerMethodField()

    class Meta:
        model = GeoreferencedCollector
        geo_field = "geom"
        fields = ["id", "collector", "catchment", "orga_level"]

    def get_catchment(self, obj):
        """Get catchment name from the collector's catchment."""
        if hasattr(obj, "catchment") and obj.catchment:
            return obj.catchment.name
        return None

    def get_orga_level(self, obj):
        """
        Determine organizational level: 'nuts', 'lau', or 'individual'.
        Based on whether the catchment's region has NUTS or LAU data.
        """
        if not hasattr(obj, "catchment") or not obj.catchment:
            return "individual"

        catchment = obj.catchment
        if not hasattr(catchment, "region") or not catchment.region:
            return "individual"

        region = catchment.region

        # Check if region has NUTS data
        try:
            if hasattr(region, "nutsregion") and region.nutsregion.nuts_id:
                return "nuts"
        except Exception:
            pass

        # Check if region has LAU data
        try:
            if hasattr(region, "lauregion") and region.lauregion.lau_id:
                return "lau"
        except Exception:
            pass

        return "individual"


class OwnedObjectModelSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = (
            "owner",
            "created_at",
            "created_by",
            "lastmodified_at",
            "lastmodified_by",
        )


class CollectorSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.Collector


class CollectionSystemSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.CollectionSystem


class SortingMethodSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = models.SortingMethod


class WasteComponentSerializer(OwnedObjectModelSerializer):
    class Meta(OwnedObjectModelSerializer.Meta):
        model = Material
        fields = ("name",)


class WasteFlyerSerializer(FieldLabelModelSerializer):
    class Meta:
        model = models.WasteFlyer
        fields = ("url",)


class WasteStreamSerializer(FieldLabelModelSerializer):
    allowed_materials = serializers.StringRelatedField(
        many=True, label="Allowed materials"
    )
    category = serializers.StringRelatedField(label="Waste category")

    class Meta:
        model = models.WasteStream
        fields = ["category", "allowed_materials"]


class CollectionModelSerializer(FieldLabelModelSerializer):
    """
    Serializer for the Collection model, including all collection parameters and waste stream fields.
    """

    id = serializers.IntegerField(label="id")
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    catchment = serializers.StringRelatedField()
    collector = serializers.StringRelatedField()
    collection_system = serializers.StringRelatedField()
    sorting_method = serializers.StringRelatedField()
    waste_category = serializers.CharField(source="waste_stream.category")
    publication_status = serializers.CharField()
    connection_type = serializers.CharField(required=False, allow_null=True)
    allowed_materials = serializers.StringRelatedField(
        many=True, source="waste_stream.allowed_materials"
    )
    forbidden_materials = serializers.StringRelatedField(
        many=True, source="waste_stream.forbidden_materials"
    )
    frequency = serializers.StringRelatedField()
    fee_system = serializers.StringRelatedField()
    min_bin_size = serializers.DecimalField(
        max_digits=8,
        decimal_places=1,
        required=False,
        allow_null=True,
    )
    required_bin_capacity = serializers.DecimalField(
        max_digits=8,
        decimal_places=1,
        required=False,
        allow_null=True,
        label="Minimum required specific bin capacity (L/reference unit)",
    )
    required_bin_capacity_reference = serializers.SerializerMethodField(
        label="Minimum required specific bin capacity reference unit"
    )
    comments = serializers.CharField(
        source="description", required=False, allow_blank=True
    )
    sources = serializers.SerializerMethodField()
    policy = serializers.SerializerMethodField()

    class Meta:
        model = models.Collection
        fields = (
            "id",
            "owner_id",
            "publication_status",
            "catchment",
            "collector",
            "collection_system",
            "sorting_method",
            "established",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "frequency",
            "fee_system",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "valid_from",
            "valid_until",
            "comments",
            "sources",
            "policy",
        )

    def get_sources(self, obj):
        return [flyer.url for flyer in obj.flyers.all() if flyer.url]

    @staticmethod
    def get_required_bin_capacity_reference(obj):
        value = obj.required_bin_capacity_reference
        if not value:
            return None
        choices = dict(models.REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES)
        return choices.get(value, value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "sources" not in data:
            data["sources"] = []
        return data

    def get_policy(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        try:
            policy = get_object_policy(user=user, obj=obj, request=request)
        except Exception:
            # Fail-closed minimal policy
            policy = {
                "can_edit": False,
                "can_delete": False,
                "can_duplicate": False,
            }
        # Return policy as-is to keep a single source of truth for key names
        return policy


class CollectionFlatSerializer(serializers.ModelSerializer):
    """
    Creates a flat, human-readable representation of Collections, suitable for file exports.
    """

    catchment = serializers.StringRelatedField(label="Catchment")
    nuts_or_lau_id = serializers.StringRelatedField(
        source="catchment.region.nuts_or_lau_id", label="NUTS/LAU Id"
    )
    country = serializers.StringRelatedField(
        source="catchment.region.country", label="Country"
    )
    collector = serializers.StringRelatedField(label="Collector")
    collection_system = serializers.StringRelatedField(label="Collection System")
    waste_category = serializers.StringRelatedField(
        source="waste_stream.category", label="Waste Category"
    )
    allowed_materials = serializers.SerializerMethodField(label="Allowed Materials")
    forbidden_materials = serializers.SerializerMethodField(label="Forbidden Materials")
    fee_system = serializers.StringRelatedField(
        source="fee_system.name", label="Fee system"
    )
    frequency = serializers.StringRelatedField(label="Frequency")
    min_bin_size = serializers.DecimalField(
        max_digits=8,
        decimal_places=1,
        required=False,
        allow_null=True,
    )
    required_bin_capacity = serializers.DecimalField(
        max_digits=8,
        decimal_places=1,
        required=False,
        allow_null=True,
        label="Minimum required specific bin capacity (L/reference unit)",
    )
    required_bin_capacity_reference = serializers.CharField(
        required=False, allow_null=True
    )
    connection_type = serializers.CharField(required=False, allow_null=True)
    comments = serializers.SerializerMethodField(source="description", label="Comments")
    flyer_urls = serializers.SerializerMethodField(label="Flyer URLs")
    bibliography_sources = serializers.SerializerMethodField(
        label="Bibliography Sources"
    )
    created_at = serializers.DateTimeField(label="Created at")

    class Meta:
        model = models.Collection
        fields = (
            "catchment",
            "nuts_or_lau_id",
            "country",
            "collector",
            "collection_system",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "fee_system",
            "frequency",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "comments",
            "flyer_urls",
            "bibliography_sources",
            "valid_from",
            "valid_until",
            "created_at",
            "lastmodified_at",
        )

    @staticmethod
    def get_allowed_materials(obj):
        return ", ".join(
            [m.name for m in obj.waste_stream.allowed_materials.all() if m.name]
        )

    @staticmethod
    def get_forbidden_materials(obj):
        return ", ".join(
            [m.name for m in obj.waste_stream.forbidden_materials.all() if m.name]
        )

    @staticmethod
    def get_flyer_urls(obj):
        return ", ".join([f.url for f in obj.flyers.all() if f.url])

    @staticmethod
    def get_bibliography_sources(obj):
        return ", ".join([str(s) for s in obj.sources.all()])

    @staticmethod
    def get_comments(obj):
        if obj.description:
            comments = obj.description
            comments = comments.replace("\r\n", "; ")
            comments = comments.replace("\r", "; ")
            comments = comments.replace("\n", "; ")
            return comments
        else:
            return ""

    @staticmethod
    def get_required_bin_capacity_reference(obj):
        value = obj.required_bin_capacity_reference
        if not value:
            return ""
        choices = dict(models.REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES)
        return choices.get(value, value)

    def to_representation(self, instance):
        # Call the superclass's to_representation method to get the default ordering
        representation = super().to_representation(instance)

        # Create an ordered dictionary to hold the ordered fields
        ordered_representation = OrderedDict()

        # Add all the fields from the superclass's representation to the ordered dictionary
        for (
            field
        ) in self.Meta.fields:  # Assuming self.Meta.fields contains the desired order
            ordered_representation[field] = representation.get(field, None)

        # --- Region attribute values (population, population density, …) ---
        region_attributes = ["Population", "Population density"]
        try:
            region = instance.catchment.region
        except AttributeError:
            region = None
        if region is not None:
            for attr_name in region_attributes:
                col_prefix = attr_name.lower().replace(" ", "_")
                rav_qs = (
                    region.regionattributevalue_set.filter(attribute__name=attr_name)
                    .select_related("attribute")
                    .order_by("date")
                )
                for rav in rav_qs:
                    year = rav.date.year if rav.date else None
                    col = f"{col_prefix}_{year}" if year else col_prefix
                    ordered_representation[col] = rav.value
                    unit = rav.attribute.unit
                    ordered_representation[f"{col}_unit"] = unit if unit else ""

        # --- Collection property values (specific waste, connection rate, …) ---
        additional_properties = ["specific waste collected", "Connection rate"]
        user = (
            getattr(self.context.get("request"), "user", None) if self.context else None
        )
        for property_name in additional_properties:
            specific_property = Property.objects.filter(name=property_name).first()
            if not specific_property:
                continue

            values = [
                value
                for value in instance.collectionpropertyvalues_for_display(user=user)
                if value.property_id == specific_property.pk
            ]

            if not values:
                values = [
                    value
                    for value in instance.aggregatedcollectionpropertyvalues_for_display(
                        user=user
                    )
                    if value.property_id == specific_property.pk
                ]
                is_aggregated = bool(values)
            else:
                is_aggregated = False

            for value in values:
                column_name = f"{property_name.lower().replace(' ', '_')}_{value.year}"
                ordered_representation[column_name] = value.average
                ordered_representation[f"{column_name}_unit"] = (
                    str(value.unit) if value.unit else ""
                )
                if is_aggregated:
                    ordered_representation["aggregated"] = True

        # Return the ordered representation
        return ordered_representation


# ---------------------------------------------------------------------------
# Import API serializer
# ---------------------------------------------------------------------------


class CollectionImportPropertyValueSerializer(serializers.Serializer):
    """A single property value to attach to an imported collection."""

    property_id = serializers.IntegerField(
        help_text="Primary key of the Property (e.g. 1=specific waste collected, 4=Connection rate)."
    )
    unit_name = serializers.CharField(
        help_text="Exact name of the Unit as stored in the database."
    )
    year = serializers.IntegerField(
        min_value=1900,
        max_value=2100,
        help_text="Measurement year.",
    )
    average = serializers.FloatField(help_text="Measured / observed value.")
    standard_deviation = serializers.FloatField(required=False, allow_null=True)


class CollectionImportRecordSerializer(serializers.Serializer):
    """
    Validates a single collection record for the bulk import endpoint.

    All lookup fields are resolved by name so the caller does not need to know
    internal primary keys.  Predecessor linking is automatic: the importer
    searches for the most recent existing collection with the same
    catchment / waste_category / collection_system and an earlier valid_from.

    Required fields
    ---------------
    nuts_or_lau_id      NUTS or LAU identifier that maps to a CollectionCatchment.
                        May be omitted only when catchment_name is provided.
    catchment_name      Exact name of a CollectionCatchment.  Used only when
                        nuts_or_lau_id is absent.
    collector_name      Exact name of the Collector.
    collection_system   Exact name of the CollectionSystem (or the alias
                        'On demand' for 'On demand kerbside collection').
    waste_category      Exact name of the WasteCategory.
    valid_from          ISO 8601 date string (YYYY-MM-DD).

    Optional fields
    ---------------
    fee_system          Exact name of the FeeSystem.
    frequency           Exact name of the CollectionFrequency.
    connection_type     One of 'mandatory', 'mandatory with exception', 'voluntary',
                        'not specified'.
    sorting_method      Exact name of the SortingMethod.
    established         Year (integer) the collection scheme was established.
    valid_until         ISO 8601 date string.
    min_bin_size        Decimal (litres).
    required_bin_capacity  Decimal (litres).
    required_bin_capacity_reference  One of 'person', 'household', 'property', 'not_specified'.
    description         Free-text comments.
    flyer_urls          List of URL strings to attach as WasteFlyers.
    property_values     List of CollectionImportPropertyValueSerializer records.
    """

    nuts_or_lau_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    catchment_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    collector_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    collection_system = serializers.CharField()
    waste_category = serializers.CharField()
    valid_from = serializers.DateField()
    valid_until = serializers.DateField(required=False, allow_null=True)

    fee_system = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    frequency = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    connection_type = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    sorting_method = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    established = serializers.IntegerField(
        required=False, allow_null=True, min_value=1900, max_value=2100
    )
    min_bin_size = serializers.DecimalField(
        required=False, allow_null=True, max_digits=8, decimal_places=1
    )
    required_bin_capacity = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=8,
        decimal_places=1,
        label="Minimum required specific bin capacity (L/reference unit)",
    )
    required_bin_capacity_reference = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    description = serializers.CharField(required=False, allow_blank=True, default="")
    flyer_urls = serializers.ListField(
        child=serializers.URLField(), required=False, default=list
    )
    property_values = CollectionImportPropertyValueSerializer(
        many=True, required=False, default=list
    )

    def validate(self, attrs):
        if not attrs.get("nuts_or_lau_id") and not attrs.get("catchment_name"):
            raise serializers.ValidationError(
                "Either 'nuts_or_lau_id' or 'catchment_name' must be provided."
            )
        return attrs
