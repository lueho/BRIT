from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Showcase
from .serializers import ShowcaseModelSerializer, ShowcaseGeoFeatureModelSerializer, ShowcaseSummaryListSerializer


class ShowcaseViewSet(ReadOnlyModelViewSet):
    queryset = Showcase.objects.all()
    filterset_fields = ('id', 'region__country')
    serializer_class = ShowcaseModelSerializer
    permission_classes = []

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        """
           Custom action to retrieve the geographical details of a Showcase instance.

           Args:
               request (Request): The HTTP request object.
               pk (int): The primary key of the Showcase instance.

           Returns:
               Response: The serialized geographical details of the Showcase instance in geoJSON format.
           """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = ShowcaseGeoFeatureModelSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summary(self, request, *args, **kwargs):
        """
        Custom action to retrieve the summary of a Showcase instance.

        Args:
            request (Request): The HTTP request object.
            pk (int): The primary key of the Showcase instance.

        Returns:
            Response: The serialized summary of the Showcase instance.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = ShowcaseSummaryListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data[0])
