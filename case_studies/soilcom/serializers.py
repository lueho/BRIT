from collections import OrderedDict

from django.urls import reverse
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from maps.models import GeoPolygon
from materials.models import Material
from utils.object_management.permissions import get_object_policy
from utils.properties.models import Property
from utils.serializers import FieldLabelModelSerializer

from . import models


class GeoreferencedWasteCollection(GeoPolygon, models.Collection):
    pass


class WasteCollectionGeometrySerializer(GeoFeatureModelSerializer):
    catchment = serializers.StringRelatedField(source="catchment.name")
    waste_category = serializers.StringRelatedField(source="waste_stream.category.name")
    collection_system = serializers.StringRelatedField(source="collection_system.name")

    class Meta:
        model = GeoreferencedWasteCollection
        geo_field = "geom"
        fields = ["id", "catchment", "waste_category", "collection_system"]


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
    )
    required_bin_capacity_reference = serializers.SerializerMethodField(
        label="Required bin capacity reference"
    )
    comments = serializers.CharField(
        source="description", required=False, allow_blank=True
    )
    sources = serializers.SerializerMethodField()
    policy = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = models.Collection
        fields = (
            "id",
            "owner_id",
            "publication_status",
            "catchment",
            "collector",
            "collection_system",
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
            "actions",
        )

    def get_sources(self, obj):
        return [flyer.url for flyer in obj.flyers.all() if flyer.url]

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

    def get_actions(self, obj):
        try:
            return {
                "detail_url": reverse("collection-detail", kwargs={"pk": obj.pk}),
                "update_url": reverse("collection-update", kwargs={"pk": obj.pk}),
                "copy_url": reverse("collection-copy", kwargs={"pk": obj.pk}),
                "delete_url": reverse("collection-delete-modal", kwargs={"pk": obj.pk}),
            }
        except Exception:
            return {}


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
    )
    required_bin_capacity_reference = serializers.CharField(
        required=False, allow_null=True
    )
    connection_type = serializers.CharField(required=False, allow_null=True)
    population = serializers.SerializerMethodField()
    population_density = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField(source="description", label="Comments")
    sources = serializers.SerializerMethodField(label="Sources")
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
            "population",
            "population_density",
            "comments",
            "sources",
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
    def get_population(obj):
        try:
            qs = obj.catchment.region.regionattributevalue_set.filter(
                attribute__name="Population"
            ).order_by("-date")
            if qs.exists():
                return int(qs[0].value)
            else:
                return None
        except AttributeError:
            return None

    @staticmethod
    def get_population_density(obj):
        qs = obj.catchment.region.regionattributevalue_set.filter(
            attribute__name="Population density"
        ).order_by("-date")
        if qs.exists():
            pd = qs[0]
            return pd.value
        else:
            return None

    @staticmethod
    def get_sources(obj):
        return ", ".join([f.url for f in obj.flyers.all() if f.url])

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

        additional_properties = ["specific waste collected", "Connection rate"]
        for property_name in additional_properties:
            # Add your custom fields at the desired position
            specific_property = Property.objects.filter(name=property_name).first()
            if specific_property:
                collection_values = models.CollectionPropertyValue.objects.filter(
                    collection=instance, property=specific_property
                )
                for value in collection_values:
                    column_name = (
                        f"{property_name.lower().replace(' ', '_')}_{value.year}"
                    )
                    ordered_representation[column_name] = value.average

                # If no CollectionPropertyValue, then fetch the AggregatedCollectionPropertyValue
                if not collection_values.exists():
                    aggregated_values = (
                        models.AggregatedCollectionPropertyValue.objects.filter(
                            collections=instance, property=specific_property
                        )
                    )
                    for value in aggregated_values:
                        column_name = (
                            f"{property_name.lower().replace(' ', '_')}_{value.year}"
                        )
                        ordered_representation[column_name] = value.average
                        # Mark this as an aggregated value
                        ordered_representation["aggregated"] = True

        # Return the ordered representation
        return ordered_representation
