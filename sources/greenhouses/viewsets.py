from django.db.models import Sum
from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.response import Response

from maps.mixins import (
    get_unbounded_geojson_rejection_response,
    get_view_geojson_bounded_query_params,
)
from sources.greenhouses.filters import NantesGreenhousesFilterSet
from sources.greenhouses.models import NantesGreenhouses
from sources.greenhouses.serializers import (
    NantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer,
)
from utils.viewsets import AutoPermModelViewSet


class NantesGreenhousesViewSet(AutoPermModelViewSet):
    """Greenhouse map/API viewset."""

    queryset = NantesGreenhouses.objects.order_by("pk")
    serializer_class = NantesGreenhousesModelSerializer
    filterset_class = NantesGreenhousesFilterSet
    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
    }

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        """Return filtered greenhouse features as GeoJSON."""

        queryset = self.filter_queryset(self.get_queryset())
        rejection_response = get_unbounded_geojson_rejection_response(
            request,
            queryset.count(),
            bounded_query_params=get_view_geojson_bounded_query_params(self),
        )
        if rejection_response is not None:
            return rejection_response

        serializer = NantesGreenhousesGeometrySerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summaries(self, request, *args, **kwargs):
        """Return summary metrics for the currently filtered greenhouse queryset."""

        queryset = self.filter_queryset(self.get_queryset())
        area = queryset.aggregate(Sum("surface_ha"))["surface_ha__sum"]
        area = str(round(area, 1)) if area else str(0)
        data = {
            "summaries": [
                {
                    "greenhouse_count": {
                        "label": "Number of greenhouses",
                        "value": f"{queryset.count()}",
                    },
                    "growth_area": {
                        "label": "Total growth area",
                        "value": f"{area} ha",
                    },
                },
            ]
        }
        return JsonResponse(data)


__all__ = ["NantesGreenhousesViewSet"]
