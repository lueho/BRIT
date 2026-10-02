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


class ShowcaseModelSerializer(ModelSerializer):
    region = RegionModelSerializer()
    catchment = CharField(source="catchment.name", default=None)
    showcase_materials = ShowcaseMaterialSerializer(many=True)
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

    def get_process_chain(self, obj):
        return [
            {"id": process.id, "name": process.name} for process in obj.process_chain
        ]

    def get_samples(self, obj):
        return [{"id": sample.id, "name": sample.name} for sample in obj.samples.all()]

    def get_sample_series(self, obj):
        return [
            {"id": series.id, "name": series.name} for series in obj.sample_series.all()
        ]

    def get_scenarios(self, obj):
        return [
            {"id": scenario.id, "name": scenario.name}
            for scenario in obj.scenarios.all()
        ]


class ShowcaseFlatSerializer(ModelSerializer):
    region = CharField(source="region.name")
    involved_processes = serializers.SerializerMethodField()

    class Meta:
        model = Showcase
        fields = ["id", "name", "region", "description", "involved_processes"]

    def get_involved_processes(self, obj):
        request = getattr(self, "request", None)
        user = getattr(request, "user", None)
        # If no request or user, treat as anonymous (no permission)
        if not (user and user.has_perm("processes.access_app_feature")):
            return []
        return [
            {
                "name": proc.name,
                "id": proc.pk,
                "url": f"/processes/types/{proc.pk}/",
            }
            for proc in obj.process_chain
        ]


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
