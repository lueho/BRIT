from rest_framework.decorators import action
from rest_framework.response import Response

from maps.mixins import (
    get_unbounded_geojson_rejection_response,
    get_view_geojson_bounded_query_params,
)
from utils.viewsets import AutoPermModelViewSet

from .models import BiogasPlantsSweden, Showcase
from .serializers import (
    BiogasPlantsSwedenSimpleModelSerializer,
    ShowcaseGeoFeatureModelSerializer,
    ShowcaseModelSerializer,
    ShowcaseSummaryListSerializer,
)


class ShowcaseViewSet(AutoPermModelViewSet):
    queryset = Showcase.objects.all()
    serializer_class = ShowcaseModelSerializer
    filterset_fields = ("id", "region__country")
    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
    }

    @action(detail=False, methods=["get"])
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
        rejection_response = get_unbounded_geojson_rejection_response(
            request,
            queryset.count(),
            bounded_query_params=get_view_geojson_bounded_query_params(self),
        )
        if rejection_response is not None:
            return rejection_response

        serializer = ShowcaseGeoFeatureModelSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summaries(self, request, *args, **kwargs):
        """
        Custom action to retrieve the summary of a Showcase instance.

        Args:
            request (Request): The HTTP request object.
            pk (int): The primary key of the Showcase instance.

        Returns:
            Response: The serialized summary of the Showcase instance.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = ShowcaseSummaryListSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data[0])


class SwedenBiogasPlantsViewSet(AutoPermModelViewSet):
    queryset = BiogasPlantsSweden.objects.all()
    serializer_class = BiogasPlantsSwedenSimpleModelSerializer
    # filterset_class = BiogasPlantsSwedenFilterSet
    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
    }
