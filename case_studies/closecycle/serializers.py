from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from rest_framework import serializers
from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.closecycle.models import Showcase
from maps.serializers import (
    BaseGeoFeatureModelSerializer,
    PolygonSerializer,
    RegionModelSerializer,
)

from .models import BiogasPlantsSweden, ShowcaseMaterial


class ShowcaseMaterialSerializer(ModelSerializer):
    material_id = serializers.IntegerField(source="material.id")
    material = CharField(source="material.name")
    role = CharField(source="get_role_display")

    class Meta:
        model = ShowcaseMaterial
        fields = ["material_id", "material", "role", "order"]


def _request_user(serializer):
    # If no request or user, treat as anonymous (no permission)
    request = serializer.context.get("request")
    return request.user if request is not None else AnonymousUser()


class ShowcaseModelSerializer(ModelSerializer):
    """Showcase with its connections, limited to records the reader may see."""

    region = RegionModelSerializer()
    catchment = serializers.SerializerMethodField()
    showcase_materials = serializers.SerializerMethodField()
    process_chain = serializers.SerializerMethodField()
    samples = serializers.SerializerMethodField()
    sample_series = serializers.SerializerMethodField()
    scenarios = serializers.SerializerMethodField()

    class Meta:
        model = Showcase
        fields = [
            "id",
            "name",
            "region",
            "catchment",
            "description",
            "showcase_materials",
            "process_chain",
            "samples",
            "sample_series",
            "scenarios",
        ]

    def get_catchment(self, obj):
        catchment = obj.visible_catchment(_request_user(self))
        return catchment.name if catchment is not None else None

    def get_showcase_materials(self, obj):
        links = obj.visible_material_links(_request_user(self))
        return ShowcaseMaterialSerializer(links, many=True).data

    def get_process_chain(self, obj):
        return [
            {"id": process.id, "name": process.name}
            for process in obj.visible_process_chain(_request_user(self))
        ]

    def get_samples(self, obj):
        return [
            {"id": sample.id, "name": sample.name}
            for sample in obj.visible_samples(_request_user(self))
        ]

    def get_sample_series(self, obj):
        return [
            {"id": series.id, "name": series.name}
            for series in obj.visible_sample_series(_request_user(self))
        ]

    def get_scenarios(self, obj):
        return [
            {"id": scenario.id, "name": scenario.name}
            for scenario in obj.visible_scenarios(_request_user(self))
        ]


class ShowcaseFlatSerializer(ModelSerializer):
    region = CharField(source="region.name", allow_null=True)
    url = serializers.SerializerMethodField()
    involved_processes = serializers.SerializerMethodField()
    input_materials = serializers.SerializerMethodField()
    intermediate_materials = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Showcase
        fields = [
            "id",
            "name",
            "region",
            "description",
            "url",
            "involved_processes",
            "input_materials",
            "intermediate_materials",
            "products",
        ]

    def _material_links_by_role(self, obj):
        """Group this showcase's visible material links by role, once per object."""
        cache = getattr(self, "_material_links_cache", None)
        if cache is None:
            cache = self._material_links_cache = {}
        if obj.pk not in cache:
            grouped = {role: [] for role in ShowcaseMaterial.Role.values}
            for link in obj.visible_material_links(_request_user(self)):
                grouped[link.role].append(link)
            cache[obj.pk] = grouped
        return cache[obj.pk]

    @staticmethod
    def _material_entries(links):
        return [
            {
                "id": link.material.pk,
                "name": link.material.name,
                "url": reverse("material-detail", args=[link.material.pk]),
            }
            for link in links
        ]

    def get_url(self, obj):
        return reverse("showcase-detail", args=[obj.pk])

    def get_involved_processes(self, obj):
        return [
            {
                "name": proc.name,
                "id": proc.pk,
                "url": reverse("processes:processtype-detail", args=[proc.pk]),
            }
            for proc in obj.visible_process_chain(_request_user(self))
        ]

    def get_input_materials(self, obj):
        links = self._material_links_by_role(obj)
        return self._material_entries(links[ShowcaseMaterial.Role.INPUT])

    def get_intermediate_materials(self, obj):
        links = self._material_links_by_role(obj)
        return self._material_entries(links[ShowcaseMaterial.Role.INTERMEDIATE])

    def get_products(self, obj):
        links = self._material_links_by_role(obj)
        return self._material_entries(links[ShowcaseMaterial.Role.PRODUCT])


class ShowcaseSummaryListSerializer(ModelSerializer):
    """Wraps the ShowcaseModelSerializer to provide a summary of the Showcase instance.
    Returns a dictionary with an entry 'summaries', which contains a list of dictionaries, which contain the summaries
     of the respective objects."""

    summaries = ShowcaseFlatSerializer(
        many=True,
        read_only=True,
        source="*",
    )

    class Meta:
        model = Showcase
        fields = ["summaries"]

    def to_representation(self, data):
        if isinstance(data, list):
            return {
                "summaries": [
                    ShowcaseFlatSerializer(instance, context=self.context).data
                    for instance in data
                ]
            }
        return {"summaries": [ShowcaseFlatSerializer(data, context=self.context).data]}


class ShowcaseGeoFeatureModelSerializer(BaseGeoFeatureModelSerializer):
    region = CharField(source="region.name")

    class Meta:
        model = Showcase
        geo_field = "geom"
        attr_path = "region.borders"
        geo_serializer_class = PolygonSerializer
        fields = [
            "id",
            "name",
            "region",
        ]


class BiogasPlantsSwedenSimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = (
            "id",
            "type",
            "county",
            "creation_year",
            "size",
            "to_upgrade",
            "main_type",
            "sub_type",
            "tech_type",
        )


class BiogasPlantsSwedenGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        geo_field = "geom"
        fields = ("id",)


class BiogasPlantsSwedenFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = (
            "id",
            "type",
            "name",
            "county",
            "city",
            "municipality",
            "creation_year",
            "size",
            "to_upgrade",
            "main_type",
            "sub_type",
            "tech_type",
        )
