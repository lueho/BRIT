import hashlib
from django.db.models import Count, Max, Min, Q
from django_filters import rest_framework as rf_filters
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.models import Collection
from case_studies.soilcom.serializers import (
    CollectionFlatSerializer,
    CollectionModelSerializer,
    WasteCollectionGeometrySerializer,
)
from maps.mixins import CachedGeoJSONMixin
from maps.utils import _generate_filter_key_part
from utils.object_management.viewsets import UserCreatedObjectViewSet


class CollectionViewSet(CachedGeoJSONMixin, UserCreatedObjectViewSet):
    """Collection viewset that integrates with GeoJSONMixin and UserCreatedObjectViewSet.

    Provides the standard CRUD operations for collections, plus:
    - GeoJSON endpoint with scope-based filtering
    - Review workflow actions (register_for_review, withdraw_from_review, approve, reject)
    - Publication status filtering based on user permissions
    """

    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    geojson_serializer_class = WasteCollectionGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = CollectionFilterSet

    def get_serializer_class(self):
        """Use detailed serializer for retrieve so the UI receives ownership and status fields.

        - retrieve -> CollectionModelSerializer (includes owner_id, publication_status, etc.)
        - default  -> self.serializer_class (CollectionFlatSerializer)
        """
        if getattr(self, "action", None) == "retrieve":
            return CollectionModelSerializer
        return super().get_serializer_class()

    # Ensure CachedGeoJSONMixin uses the GeoJSON serializer class
    def get_geojson_serializer_class(self):
        return WasteCollectionGeometrySerializer

    def _compute_dataset_version(self, request) -> str:
        """Compute a scope-aware dataset version for Collections.

        Uses COUNT, MAX(lastmodified_at), MIN(id), MAX(id) over a queryset constrained by scope and user.
        """
        scope = (request.query_params.get("scope") or "published").lower()
        user = getattr(request, "user", None)
        qs = Collection.objects.all()

        if scope == "published":
            qs = qs.filter(publication_status="published")
        elif scope == "private":
            if user and user.is_authenticated and not getattr(user, "is_staff", False):
                qs = qs.filter(owner=user)
        elif scope == "review":
            if user and user.is_authenticated and not getattr(user, "is_staff", False):
                qs = qs.filter(Q(owner=user) | Q(publication_status="review"))
            else:
                qs = qs.filter(publication_status="review")

        agg = qs.aggregate(
            cnt=Count("pk"),
            max_mod=Max("lastmodified_at"),
            min_id=Min("pk"),
            max_id=Max("pk"),
        )
        cnt = agg.get("cnt") or 0
        max_mod = agg.get("max_mod")
        ts = int(max_mod.timestamp()) if max_mod else 0
        min_id = agg.get("min_id") or 0
        max_id = agg.get("max_id") or 0
        base = f"{scope}:{cnt}:{ts}:{min_id}:{max_id}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    def get_cache_key(self, request):
        """Build a deterministic cache key including filters and dataset version.

        Format examples:
        - collection_geojson:id:1,2,3:dv:abc123def456
        - collection_geojson:filter:<hash>:dv:abc123def456
        """
        params = request.query_params

        # Dataset version should be server-computed for safety
        dv = self._compute_dataset_version(request)

        # If specific IDs are requested, build an ID-specific key
        id_list = params.getlist("id") if hasattr(params, "getlist") else []
        if id_list:
            try:
                ids_sorted = sorted([str(int(x)) for x in id_list])
            except Exception:
                ids_sorted = sorted([str(x) for x in id_list])
            return f"collection_geojson:id:{','.join(ids_sorted)}:dv:{dv}"

        # Build filter dict, excluding transient or non-data keys
        exclude_keys = {"csrfmiddlewaretoken", "page", "next", "dv"}
        filters = {}
        for key in params.keys():
            if key in exclude_keys:
                continue
            values = params.getlist(key) if hasattr(params, "getlist") else [params.get(key)]
            # Normalize singletons to string, multi-values to list
            if len(values) == 1:
                filters[key] = values[0]
            elif len(values) > 1:
                filters[key] = sorted(values)

        filter_part = _generate_filter_key_part(filters)
        return f"collection_geojson:filter:{filter_part}:dv:{dv}"

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def summaries(self, request, *args, **kwargs):
        self.check_permissions(request)
        queryset = self.get_queryset().filter(id__in=request.query_params.getlist("id"))
        serializer = CollectionModelSerializer(
            queryset,
            many=True,
            field_labels_as_keys=True,
            context={"request": request},
        )
        return Response({"summaries": serializer.data})

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def geojson(self, request, *args, **kwargs):
        """GeoJSON endpoint with the same permission checks as standard endpoints."""
        return super().geojson(request, *args, **kwargs)
