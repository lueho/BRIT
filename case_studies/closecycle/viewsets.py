import hashlib

from django.db.models import (
    BigIntegerField,
    CharField,
    OuterRef,
    StringAgg,
    Subquery,
    Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast, Concat
from rest_framework.decorators import action
from rest_framework.response import Response

from maps.mixins import (
    CachedGeoJSONMixin,
    get_unbounded_geojson_rejection_response,
    get_view_geojson_bounded_query_params,
)
from maps.models import Catchment, GeoPolygon, Region
from maps.throttling import GeoJSONAnonThrottle
from utils.object_management.permissions import filter_queryset_for_user
from utils.viewsets import AutoPermModelViewSet

from .filters import ShowcaseAPIFilterSet
from .models import BiogasPlantsSweden, Showcase
from .serializers import (
    BiogasPlantsSwedenSimpleModelSerializer,
    ShowcaseFlatSerializer,
    ShowcaseGeoFeatureModelSerializer,
    ShowcaseModelSerializer,
    pilot_region_features,
    visible_region_ids,
)


class ShowcaseViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    queryset = Showcase.objects.all()
    serializer_class = ShowcaseModelSerializer
    filterset_fields = ("id", "region__country")
    filterset_class = ShowcaseAPIFilterSet
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
            ("material_links", "process_links", "catchment")
            if self.action == "summaries"
            else None
        )
        return Showcase.prefetch_visible_connections(
            queryset, self.request.user, connections=connections
        )

    @staticmethod
    def _row_xmin(model, pk_ref):
        """Transaction id of the ``model`` row at ``pk_ref`` as text."""
        return Cast(
            Subquery(
                model.objects.filter(pk=OuterRef(pk_ref))
                .annotate(
                    row_xmin=RawSQL(
                        "xmin::text::bigint", [], output_field=BigIntegerField()
                    )
                )
                .values("row_xmin")[:1]
            ),
            CharField(),
        )

    def _version_aggregates(self):
        """Showcase GeoJSON also serializes the linked catchments, regions and
        their borders as pilot polygons. Max aggregates over those rows miss
        edits to any row but the newest one, so the version fingerprints
        every linked row by its modification time and its transaction id, which
        changes on each update however the row was written."""
        linked_rows = (
            (Region, "region_id", "region__lastmodified_at"),
            (GeoPolygon, "region__borders_id", None),
            (Catchment, "catchment_id", "catchment__lastmodified_at"),
            (Region, "catchment__region_id", "catchment__region__lastmodified_at"),
            (GeoPolygon, "catchment__region__borders_id", None),
        )
        parts = [Cast("pk", CharField()), Value("#"), Cast("theme", CharField())]
        for model, pk_ref, modified_ref in linked_rows:
            parts += [Value(":"), self._row_xmin(model, pk_ref)]
            if modified_ref:
                parts += [Value("@"), Cast(modified_ref, CharField())]
        return {
            **super()._version_aggregates(),
            "pilot_fingerprint": StringAgg(
                Concat(*parts, output_field=CharField()),
                Value(";"),
                order_by="pk",
            ),
        }

    def _version_timestamp(self, agg):
        # Full-precision timestamp, so edits within one second still rotate.
        max_mod = agg.get("max_mod")
        fingerprint = agg.get("pilot_fingerprint") or ""
        return ":".join(
            (
                "pilot-regions-v1:theme-context-v1:code-labels-v1",
                max_mod.isoformat() if max_mod else "",
                hashlib.sha1(fingerprint.encode("utf-8")).hexdigest(),
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
            queryset,
            many=True,
            context={
                "request": request,
                "visible_region_ids": visible_region_ids(queryset, request.user),
            },
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
        context = self.get_serializer_context()
        context["visible_region_ids"] = visible_region_ids(queryset, request.user)
        serializer = ShowcaseFlatSerializer(queryset, many=True, context=context)
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
