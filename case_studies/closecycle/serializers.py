from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from rest_framework import serializers
from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.closecycle.models import Showcase
from maps.models import Catchment, Region
from maps.serializers import (
    BaseGeoFeatureModelSerializer,
    RegionModelSerializer,
    get_nested_attr,
)
from utils.object_management.permissions import filter_queryset_for_user

from .models import BiogasPlantsSweden, ShowcaseMaterial
from .themes import pilot_region_info


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


class ShowcaseContextMixin:
    def get_pilot_region(self, obj):
        catchment = obj.visible_catchment(_request_user(self))
        return pilot_region_info(catchment) if catchment is not None else None


class ShowcaseModelSerializer(ShowcaseContextMixin, ModelSerializer):
    """Showcase with its connections, limited to records the reader may see."""

    region = RegionModelSerializer()
    geom = GeometryField(allow_null=True, read_only=True)
    theme_details = serializers.ReadOnlyField(source="theme_info")
    pilot_region = serializers.SerializerMethodField()
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
            "geom",
            "theme",
            "theme_details",
            "pilot_region",
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


class ShowcaseFlatSerializer(ShowcaseContextMixin, ModelSerializer):
    region = CharField(source="region.name", allow_null=True)
    theme = serializers.ReadOnlyField(source="theme_info")
    pilot_region = serializers.SerializerMethodField()
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
            "theme",
            "pilot_region",
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
    region = CharField(source="region.name", allow_null=True)
    code = serializers.ReadOnlyField()
    theme = serializers.ReadOnlyField(source="theme_info")
    feature_type = serializers.SerializerMethodField()

    class Meta:
        model = Showcase
        geo_field = "geom"
        fields = [
            "id",
            "name",
            "code",
            "region",
            "theme",
            "feature_type",
        ]

    def get_geom(self, obj):
        geom = obj.geom
        if geom is None:
            borders = get_nested_attr(obj, "region.borders")
            if borders is not None and borders.geom:
                geom = borders.geom.centroid
        if geom is None:
            return None
        return GeometryField().to_representation(geom)

    def get_feature_type(self, obj):
        return "showcase"


def _pilot_geometry(region):
    borders = getattr(region, "borders", None)
    geom = getattr(borders, "geom", None)
    if geom is None or geom.empty:
        return None
    return geom


def pilot_region_features(showcases, user):
    """GeoJSON features for the TBN pilot regions of ``showcases``.

    Each visible catchment shared by the showcases contributes a single
    MultiPolygon feature listing its associated showcases. Showcases without
    a catchment fall back to their visible region. A showcase linked to a
    catchment the user may not see contributes no pilot region at all, so a
    private catchment's geometry is never exposed.
    """
    showcases = list(showcases)
    catchments = {
        catchment.pk: catchment
        for catchment in filter_queryset_for_user(
            Catchment.objects.filter(
                pk__in={s.catchment_id for s in showcases if s.catchment_id}
            ),
            user,
        ).select_related("region__borders")
    }
    regions = {
        region.pk: region
        for region in filter_queryset_for_user(
            Region.objects.filter(
                pk__in={
                    s.region_id for s in showcases if s.region_id and not s.catchment_id
                }
                | {c.region_id for c in catchments.values() if c.region_id}
            ),
            user,
        ).select_related("borders")
    }

    pilots = {}
    for showcase in showcases:
        if showcase.catchment_id:
            catchment = catchments.get(showcase.catchment_id)
            region = catchment and regions.get(catchment.region_id)
            if region is None:
                continue
            key = f"pilot-catchment-{catchment.pk}"
            name = str(catchment)
            geometry = _pilot_geometry(region)
            context = pilot_region_info(catchment)
        elif showcase.region_id:
            region = regions.get(showcase.region_id)
            if region is None:
                continue
            key = f"pilot-region-{region.pk}"
            name = str(region)
            geometry = _pilot_geometry(region)
            context = None
        else:
            continue
        pilot = pilots.setdefault(
            key,
            {
                "name": name,
                "geometry": geometry,
                "showcases": [],
                "themes": {},
                "pilot_region": context,
            },
        )
        if showcase.theme_info:
            pilot["themes"][showcase.theme] = showcase.theme_info
        pilot["showcases"].append(
            {
                "id": showcase.pk,
                "name": showcase.name,
                "region": showcase.region.name if showcase.region else None,
            }
        )

    geometry_field = GeometryField()
    return [
        {
            "type": "Feature",
            "id": key,
            "geometry": geometry_field.to_representation(pilot["geometry"]),
            "properties": {
                "feature_type": "pilot_region",
                "name": pilot["name"],
                "region": pilot["name"],
                "pilot_region": pilot["pilot_region"],
                "themes": list(pilot["themes"].values()),
                "theme": next(iter(pilot["themes"].values()))
                if len(pilot["themes"]) == 1
                else None,
                "showcases": pilot["showcases"],
            },
        }
        for key, pilot in pilots.items()
        if pilot["geometry"] is not None
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
