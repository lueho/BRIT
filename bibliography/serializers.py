from rest_framework.serializers import ModelSerializer, HyperlinkedIdentityField

from .models import Source


class SourceAbbreviationSerializer(ModelSerializer):

    class Meta:
        model = Source
        fields = ('pk', 'abbreviation')
