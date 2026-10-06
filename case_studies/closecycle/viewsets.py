from django.db.models import BigIntegerField, Max, OuterRef, Subquery
from django.db.models.expressions import RawSQL
from rest_framework.decorators import action
from rest_framework.response import Response

from maps.mixins import (
    CachedGeoJSONMixin,
    get_unbounded_geojson_rejection_response,
    get_view_geojson_bounded_query_params,
)
from maps.models import GeoPolygon
from maps.throttling import GeoJSONAnonThrottle
from utils.object_management.permissions import filter_queryset_for_user
from utils.viewsets import AutoPermModelViewSet

from .models import BiogasPlantsSweden, Showcase
from .serializers import (
    BiogasPlantsSwedenSimpleModelSerializer,
    ShowcaseFlatSerializer,
    ShowcaseGeoFeatureModelSerializer,
    ShowcaseModelSerializer,
    pilot_region_features,
)


class ShowcaseViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    queryset = Showcase.objects.all()
    serializer_class = ShowcaseModelSerializer
    filterset_fields = ("id", "region__country")
    geojson_throttle_classes = (GeoJSONAnonThrottle,)
    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
        "version": None,
    }

    def get_queryset(self):
        queryset = filter_queryset_for_user(
            super().get_queryset(), self.request.user
        ).select_related("region__borders")
        if self.action in ("geojson", "version"):
            return queryset
        connections = (
            ("material_links", "process_links") if self.action == "summaries" else None
        )
        return Showcase.prefetch_visible_connections(
            queryset, self.request.user, connections=connections
        )

    def _version_aggregates(self):
        """Showcase GeoJSON serializes the related Region's name and borders,
        so the version also tracks the Region modification time and the
        newest transaction id of the border rows, which are edited in place
        and carry no timestamp of their own."""
        borders_xmin = (
            GeoPolygon.objects.filter(pk=OuterRef("region__borders_id"))
            .annotate(
                row_xmin=RawSQL(
                    "xmin::text::bigint", [], output_field=BigIntegerField()
                )
            )
            .values("row_xmin")[:1]
        )
        catchment_borders_xmin = (
            GeoPolygon.objects.filter(pk=OuterRef("catchment__region__borders_id"))
            .annotate(
                row_xmin=RawSQL(
                    "xmin::text::bigint", [], output_field=BigIntegerField()
                )
            )
            .values("row_xmin")[:1]
        )
        return {
            **super()._version_aggregates(),
            "max_region_mod": Max("region__lastmodified_at"),
            "max_borders_xmin": Max(Subquery(borders_xmin)),
            "max_catchment_mod": Max("catchment__lastmodified_at"),
            "max_catchment_region_mod": Max("catchment__region__lastmodified_at"),
            "max_catchment_borders_xmin": Max(Subquery(catchment_borders_xmin)),
        }

    def _version_timestamp(self, agg):
        # Full-precision timestamps, so edits within one second still rotate.
        max_mod = agg.get("max_mod")
        region_mod = agg.get("max_region_mod")
        catchment_mod = agg.get("max_catchment_mod")
        catchment_region_mod = agg.get("max_catchment_region_mod")
        return ":".join(
            (
                "pilot-regions-v1",
                max_mod.isoformat() if max_mod else "",
                region_mod.isoformat() if region_mod else "",
                str(agg.get("max_borders_xmin") or 0),
                catchment_mod.isoformat() if catchment_mod else "",
                catchment_region_mod.isoformat() if catchment_region_mod else "",
                str(agg.get("max_catchment_borders_xmin") or 0),
            )
        )

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
        data = serializer.data
        pilots = pilot_region_features(queryset, request.user)
        if pilots:
            data = {**data, "features": pilots + list(data["features"])}
        response = Response(data)
        # Lets the client's IndexedDB cache revalidate via the version action.
        response["X-Data-Version"] = self.get_dataset_version(request)
        response["Access-Control-Expose-Headers"] = "X-Data-Version"
        return response

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
        serializer = ShowcaseFlatSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response({"summaries": serializer.data})


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
