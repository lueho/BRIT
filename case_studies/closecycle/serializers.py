from rest_framework import serializers
from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from case_studies.closecycle.models import Showcase
from maps.serializers import BaseGeoFeatureModelSerializer, PolygonSerializer, RegionModelSerializer
from .models import BiogasPlantsSweden

from django.conf import settings
from processes.views import MOCK_PROCESS_TYPES




class ShowcaseModelSerializer(ModelSerializer):
    region = RegionModelSerializer()

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description']


class ShowcaseFlatSerializer(ModelSerializer):
    region = CharField(source='region.name')
    involved_processes = serializers.SerializerMethodField()

    class Meta:
        model = Showcase
        fields = ['id', 'name', 'region', 'description', 'involved_processes']

    def get_involved_processes(self, obj):
        # Hybrid mock: Showcase name to involved process names (keep in sync with view)
        SHOWCASE_PROCESS_MAP = {
            "Municipality & farms 1": ["Anaerobic Digestion", "Composting"],
            "Agricultural Education": ["Anaerobic Digestion", "Pyrolysis", "Composting"],
        }
        if not self.request.user.has_perm('processes.access_app_feature'):
            return []
        showcase_name = getattr(obj, "name", None)
        involved_processes = []
        if showcase_name in SHOWCASE_PROCESS_MAP:
            process_names = SHOWCASE_PROCESS_MAP[showcase_name]
            for pname in process_names:
                proc = next((p for p in MOCK_PROCESS_TYPES if p["name"] == pname), None)
                if proc:
                    involved_processes.append({
                        "name": proc["name"],
                        "id": proc["id"],
                        "url": f"/processes/types/{proc['id']}/"
                    })
        return involved_processes


class ShowcaseSummaryListSerializer(ModelSerializer):
    """Wraps the ShowcaseModelSerializer to provide a summary of the Showcase instance.
    Returns a dictionary with an entry 'summaries', which contains a list of dictionaries, which contain the summaries
     of the respective objects."""
    summaries = ShowcaseFlatSerializer(many=True, read_only=True, source='*')

    class Meta:
        model = Showcase
        fields = ['summaries']

    def to_representation(self, data):
        # Get the context from the parent serializer
        context = self.context 
        if isinstance(data, list):
            return {'summaries': [ShowcaseFlatSerializer(instance, context=context).data for instance in data]}
        return {'summaries': [ShowcaseFlatSerializer(data, context=context).data]}


class ShowcaseGeoFeatureModelSerializer(BaseGeoFeatureModelSerializer):
    region = CharField(source='region.name')

    class Meta:
        model = Showcase
        geo_field = 'geom'
        attr_path = 'region.borders'
        geo_serializer_class = PolygonSerializer
        fields = ['id', 'name', 'region',]


class BiogasPlantsSwedenSimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = ('id', 'type', 'county', 'creation_year', 'size', 'to_upgrade', 'main_type', 'sub_type', 'tech_type',)


class BiogasPlantsSwedenGeometrySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        geo_field = 'geom'
        fields = ('id',)


class BiogasPlantsSwedenFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiogasPlantsSweden
        fields = (
            'id', 'type', 'name', 'county', 'city', 'municipality', 'creation_year', 'size', 'to_upgrade', 'main_type',
            'sub_type', 'tech_type'
        )
