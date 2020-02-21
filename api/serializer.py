from rest_framework_git.serializers import GeoFeatureModelSerializer
from .models import TreeCollection

class TreeCollectionSerializer(GeoFeatureModelSerializer):

    class Meta:
        model = TreeCollection
        geo_field = 'location'
        fields = ('id',)