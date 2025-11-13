from django.db.models import Sum
from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.response import Response

from utils.viewsets import AutoPermModelViewSet

from .filters import NantesGreenhousesFilterSet
from .models import NantesGreenhouses
from .serializers import (
    NantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer,
)


class NantesGreenhousesViewSet(AutoPermModelViewSet):
    queryset = NantesGreenhouses.objects.all()
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
        queryset = self.filter_queryset(self.get_queryset())
        serializer = NantesGreenhousesGeometrySerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summaries(self, request, *args, **kwargs):
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
