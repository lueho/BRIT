from rest_framework import serializers
from rest_framework_gis.fields import GeometrySerializerMethodField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.soilcom.models import CollectionCatchment

# Geometry simplification tolerance in degrees (approx 100m at equator)
# Lower values = more detail, higher values = more simplification
GEOMETRY_SIMPLIFY_TOLERANCE = 0.001


class CatchmentGeometrySerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for catchments that have waste collections.

    Returns catchment id, name, type, and the region border geometry.
    Supports optional geometry simplification via the ``simplified_geom``
    annotation added by the viewset queryset.
    """

    catchment_id = serializers.IntegerField(source="id")
    catchment_name = serializers.CharField(source="name")
    catchment_type = serializers.CharField(source="type")
    geom = GeometrySerializerMethodField()

    class Meta:
        model = CollectionCatchment
        geo_field = "geom"
        fields = ["catchment_id", "catchment_name", "catchment_type"]

    def get_geom(self, instance):
        """Return simplified geometry if available, otherwise original."""
        if hasattr(instance, "simplified_geom") and instance.simplified_geom:
            return instance.simplified_geom
        return getattr(instance, "geom", None)


class CatchmentPopulationSerializer(serializers.Serializer):
    """Flat JSON serializer for catchment population / population density."""

    catchment_id = serializers.IntegerField()
    population = serializers.FloatField(allow_null=True)
    population_density = serializers.FloatField(allow_null=True)


class CatchmentOrgaLevelSerializer(serializers.Serializer):
    """Flat JSON serializer for catchment organizational level (Karte 1)."""

    catchment_id = serializers.IntegerField()
    orga_level = serializers.CharField()


class CatchmentCollectionSystemSerializer(serializers.Serializer):
    """Flat JSON serializer for catchment collection system (Karte 2)."""

    catchment_id = serializers.IntegerField()
    collection_system = serializers.CharField()


class CatchmentCollectionSystemCountSerializer(serializers.Serializer):
    """Flat JSON serializer for number of collection systems per catchment."""

    catchment_id = serializers.IntegerField()
    collection_system_count = serializers.IntegerField()


class CatchmentConnectionRateSerializer(serializers.Serializer):
    """Flat JSON serializer for catchment connection rate (Karte 3)."""

    catchment_id = serializers.IntegerField()
    connection_rate = serializers.FloatField(allow_null=True)
    is_door_to_door = serializers.BooleanField()


class CatchmentFoodWasteCategorySerializer(serializers.Serializer):
    """Flat JSON serializer for allowed food waste in biowaste (Karte 4)."""

    catchment_id = serializers.IntegerField()
    food_waste_category = serializers.CharField()


class CatchmentMaterialStatusSerializer(serializers.Serializer):
    """Flat JSON serializer for material allowed/forbidden status (Karte 5, 6)."""

    catchment_id = serializers.IntegerField()
    status = serializers.CharField()


class CatchmentCollectionSupportSerializer(serializers.Serializer):
    """Flat JSON serializer for combined paper + plastic bags status (Karte 7)."""

    catchment_id = serializers.IntegerField()
    paper_bags = serializers.CharField()
    plastic_bags = serializers.CharField()


class CatchmentFrequencyTypeSerializer(serializers.Serializer):
    """Flat JSON serializer for collection frequency type (Karte 8, 9)."""

    catchment_id = serializers.IntegerField()
    frequency_type = serializers.CharField()


class CatchmentCombinedFrequencySerializer(serializers.Serializer):
    """Flat JSON serializer for combined bio + residual frequency (Karte 10)."""

    catchment_id = serializers.IntegerField()
    bio_frequency = serializers.CharField()
    residual_frequency = serializers.CharField()


class CatchmentCollectionCountSerializer(serializers.Serializer):
    """Flat JSON serializer for annual collection count (Karte 11, 12)."""

    catchment_id = serializers.IntegerField()
    collection_count = serializers.IntegerField(allow_null=True)
    has_seasonal_variation = serializers.BooleanField()


class CatchmentCombinedCollectionCountSerializer(serializers.Serializer):
    """Flat JSON serializer for combined bio + residual collection count (Karte 13)."""

    catchment_id = serializers.IntegerField()
    bio_count = serializers.IntegerField(allow_null=True)
    residual_count = serializers.IntegerField(allow_null=True)


class CatchmentFeeSystemSerializer(serializers.Serializer):
    """Flat JSON serializer for fee system (Karte 14, 15)."""

    catchment_id = serializers.IntegerField()
    fee_system = serializers.CharField()


class CatchmentCombinedFeeSystemSerializer(serializers.Serializer):
    """Flat JSON serializer for combined bio + residual fee system (Karte 16)."""

    catchment_id = serializers.IntegerField()
    bio_fee = serializers.CharField()
    residual_fee = serializers.CharField()


class CatchmentCollectionAmountSerializer(serializers.Serializer):
    """Flat JSON serializer for specific waste collected amount (Karte 17, 18)."""

    catchment_id = serializers.IntegerField()
    amount = serializers.FloatField(allow_null=True)
    no_collection = serializers.BooleanField(default=False)


class CatchmentWasteRatioSerializer(serializers.Serializer):
    """Flat JSON serializer for biowaste / total ratio (Karte 19)."""

    catchment_id = serializers.IntegerField()
    bio_amount = serializers.FloatField(allow_null=True)
    residual_amount = serializers.FloatField(allow_null=True)
    ratio = serializers.FloatField(allow_null=True)


class CatchmentOrganicRatioSerializer(serializers.Serializer):
    """Flat JSON serializer for organic / (organic + residual) ratio (Karte 28)."""

    catchment_id = serializers.IntegerField()
    organic_amount = serializers.FloatField(allow_null=True)
    residual_amount = serializers.FloatField(allow_null=True)
    ratio = serializers.FloatField(allow_null=True)


class CatchmentMinBinSizeSerializer(serializers.Serializer):
    """Flat JSON serializer for minimum bin size per catchment (Karte 23, 24)."""

    catchment_id = serializers.IntegerField()
    min_bin_size = serializers.FloatField(allow_null=True)


class CatchmentRequiredBinCapacitySerializer(serializers.Serializer):
    """Flat JSON serializer for required specific bin capacity (Karte 25, 26)."""

    catchment_id = serializers.IntegerField()
    required_bin_capacity = serializers.FloatField(allow_null=True)
    required_bin_capacity_reference = serializers.CharField(allow_null=True)
