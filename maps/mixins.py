import hashlib
import json

from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.core.cache import caches
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Max, Min
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

# Threshold for switching to streaming response (number of features)
STREAMING_THRESHOLD = 1000

# Enable streaming for large uncached requests
STREAMING_ENABLED = True

MAX_UNBOUNDED_GEOJSON_FEATURES = getattr(
    settings, "GEOJSON_MAX_UNBOUNDED_FEATURES", 5000
)
GEOJSON_CONTROL_QUERY_PARAMS = {
    "csrfmiddlewaretoken",
    "dv",
    "format",
    "next",
    "page",
    "scope",
    "stream",
}


def is_bounded_geojson_request(request, *, bbox=None):
    if bbox is not None:
        return True

    bounded_query_params = get_view_geojson_bounded_query_params(None)
    return has_bounded_geojson_query_param(
        request, bounded_query_params=bounded_query_params
    )


def has_bounded_geojson_query_param(request, *, bounded_query_params):
    params = getattr(request, "query_params", None) or getattr(request, "GET", {})
    for key in params.keys():
        if key in GEOJSON_CONTROL_QUERY_PARAMS or key == "bbox":
            continue
        if key not in bounded_query_params:
            continue

        values = (
            params.getlist(key) if hasattr(params, "getlist") else [params.get(key)]
        )
        if any(str(value).strip() for value in values if value is not None):
            return True

    return False


def get_view_geojson_bounded_query_params(view):
    bounded_query_params = {"id", "bbox"}
    if view is None:
        return bounded_query_params

    filterset_fields = getattr(view, "filterset_fields", None)
    if isinstance(filterset_fields, dict):
        bounded_query_params.update(filterset_fields)
    elif filterset_fields:
        bounded_query_params.update(filterset_fields)

    filterset_class = getattr(view, "filterset_class", None)
    if filterset_class is not None:
        bounded_query_params.update(getattr(filterset_class, "base_filters", {}).keys())

    return bounded_query_params


def get_unbounded_geojson_rejection_response(
    request,
    count,
    *,
    bbox=None,
    bounded_query_params=None,
    max_features=None,
):
    max_features = (
        MAX_UNBOUNDED_GEOJSON_FEATURES if max_features is None else max_features
    )
    if (
        max_features is None
        or count <= max_features
        or bbox is not None
        or has_bounded_geojson_query_param(
            request,
            bounded_query_params=(
                get_view_geojson_bounded_query_params(None)
                if bounded_query_params is None
                else bounded_query_params
            ),
        )
    ):
        return None

    response = Response(
        {
            "detail": (
                "Unbounded GeoJSON requests above "
                f"{max_features} features are not allowed. Provide an id, bbox, "
                "or endpoint-specific filter."
            )
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
    response["X-Cache-Status"] = "REJECT"
    response["X-Total-Count"] = str(count)
    response["Access-Control-Expose-Headers"] = "X-Total-Count, X-Cache-Status"
    return response


class CachedGeoJSONMixin:
    """
    Mixin to add caching to GeoJSON endpoints using the get_or_set_cache helper.
    Requires the ViewSet to implement `get_cache_key(self, request)`
    and `get_geojson_serializer_class(self)`.

    Supports optional bounding box filtering via `bbox` query parameter.
    For large datasets, uses streaming response to reduce memory pressure.
    """

    # Default cache timeout for this mixin - can be overridden in ViewSet
    max_unbounded_geojson_features = MAX_UNBOUNDED_GEOJSON_FEATURES
    cache_timeout = (
        getattr(settings, "CACHES", {})
        .get(getattr(settings, "GEOJSON_CACHE", "default"), {})
        .get("TIMEOUT", 3600)
    )  # Default 1 hour fallback

    def _parse_bbox(self, request):
        """Parse bounding box from request query params.

        Expected format: bbox=minLng,minLat,maxLng,maxLat
        Returns a Polygon or None if not provided/invalid.
        """
        bbox_str = request.query_params.get("bbox")
        if not bbox_str:
            return None
        try:
            coords = [float(x) for x in bbox_str.split(",")]
            if len(coords) != 4:
                return None
            min_lng, min_lat, max_lng, max_lat = coords
            return Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
        except (ValueError, TypeError):
            return None

    def _apply_bbox_filter(self, queryset, bbox):
        """Apply bounding box filter to queryset if bbox is provided."""
        if bbox is None:
            return queryset
        # Try common geometry field names
        for field in ["geom", "geometry", "catchment__region__borders__geom"]:
            if hasattr(queryset.model, field.split("__")[0]):
                return queryset.filter(**{f"{field}__intersects": bbox})
        return queryset

    def get_geojson_queryset_with_bbox(self, request):
        """Get queryset with optional bbox filtering."""
        if hasattr(self, "get_geojson_queryset"):
            queryset = self.filter_queryset(self.get_geojson_queryset())
        else:
            queryset = self.filter_queryset(self.get_queryset())

        queryset = self._apply_id_filter(queryset, request)
        bbox = self._parse_bbox(request)
        if bbox:
            queryset = self._apply_bbox_filter(queryset, bbox)
        return queryset

    def _apply_id_filter(self, queryset, request):
        params = getattr(request, "query_params", None) or getattr(request, "GET", {})
        values = (
            params.getlist("id") if hasattr(params, "getlist") else [params.get("id")]
        )
        values = [value for value in values if value is not None and str(value).strip()]
        if not values:
            return queryset
        try:
            return queryset.filter(pk__in=values)
        except (DjangoValidationError, TypeError, ValueError):
            return queryset.none()

    def get_geojson_data(self):
        """Generates the GeoJSON data. Expected to be called on cache miss."""
        queryset = self.get_geojson_queryset_with_bbox(self.request)
        serializer_class = getattr(
            self, "get_geojson_serializer_class", self.get_serializer_class
        )
        serializer = serializer_class()(
            queryset, many=True, context={"request": self.request}
        )
        return serializer.data

    def get_dataset_version(self, request):
        """Return a short hash representing the current dataset state.

        Computes a version based on count, max lastmodified_at, and ID range.
        ViewSets may override this to include additional dependencies (e.g.,
        related model timestamps).

        Falls back to get_cache_key if the model lacks lastmodified_at.
        """
        queryset = self.get_geojson_queryset_with_bbox(request)
        model = queryset.model

        # Check if model has lastmodified_at field
        field_names = [f.name for f in model._meta.get_fields()]
        if "lastmodified_at" not in field_names:
            # Fallback to cache key for models without timestamp
            if hasattr(self, "get_cache_key"):
                return self.get_cache_key(request)
            return "unknown"

        agg = queryset.aggregate(
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
        base = f"{cnt}:{ts}:{min_id}:{max_id}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    def _stream_geojson(self, queryset):
        """Generator that streams GeoJSON features to reduce memory usage.

        Yields the GeoJSON structure piece by piece, serializing features
        one at a time to avoid loading all data into memory.
        """
        # Get the serializer class (not instance)
        get_serializer_class = getattr(
            self, "get_geojson_serializer_class", self.get_serializer_class
        )
        serializer_class = get_serializer_class()

        yield '{"type": "FeatureCollection", "features": ['

        first = True
        for obj in queryset.iterator(chunk_size=100):
            if not first:
                yield ","
            first = False
            # Serialize single feature
            try:
                serializer = serializer_class(obj, context={"request": self.request})
                yield json.dumps(serializer.data)
            except Exception as e:
                # Log error but continue streaming
                import logging

                logging.getLogger(__name__).warning(
                    "Error serializing feature %s: %s", getattr(obj, "pk", "?"), e
                )
                continue

        yield "]}"

    @action(detail=False, methods=["get", "head"])
    def version(self, request, *args, **kwargs):
        """Return the current dataset version for client-side cache validation.

        This lightweight endpoint allows clients to check if their cached data
        is still valid without fetching the full dataset. Returns a version hash
        that changes when the underlying data changes.

        Clients should store this version alongside cached data and compare
        before using cached results.
        """
        version = self.get_dataset_version(request)
        response = Response({"version": version})
        response["X-Data-Version"] = version
        response["Cache-Control"] = "no-cache"  # Always validate
        return response

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        # Ensure ViewSet implements get_cache_key or adapt as needed
        if not hasattr(self, "get_cache_key"):
            raise NotImplementedError(
                "ViewSet must implement get_cache_key when using CachedGeoJSONMixin"
            )

        # Check for streaming preference
        use_stream = request.query_params.get("stream", "").lower() == "true"
        bbox = self._parse_bbox(request)
        cache_key = self.get_cache_key(request)

        # Try cache first (unless streaming is explicitly requested)
        if not use_stream and not bbox:
            data = caches[getattr(settings, "GEOJSON_CACHE", "default")].get(cache_key)

            if data is not None:
                data_version = self.get_dataset_version(request)
                response = Response(data)
                response["X-Cache-Status"] = "HIT"
                # Add feature count for frontend progress
                if isinstance(data, dict) and "features" in data:
                    response["X-Total-Count"] = str(len(data["features"]))
                # Add version header for client-side cache validation
                response["X-Data-Version"] = data_version
                response["Access-Control-Expose-Headers"] = (
                    "X-Total-Count, X-Cache-Status, X-Data-Version"
                )
                return response

        # Cache miss or streaming requested - get queryset
        queryset = self.get_geojson_queryset_with_bbox(request)
        count = queryset.count()
        rejection_response = get_unbounded_geojson_rejection_response(
            request,
            count,
            bbox=bbox,
            bounded_query_params=get_view_geojson_bounded_query_params(self),
            max_features=self.max_unbounded_geojson_features,
        )
        if rejection_response is not None:
            return rejection_response

        data_version = self.get_dataset_version(request)

        # Use streaming for large datasets to prevent memory issues
        if STREAMING_ENABLED and count > STREAMING_THRESHOLD:
            response = StreamingHttpResponse(
                self._stream_geojson(queryset),
                content_type="application/geo+json",
            )
            response["X-Cache-Status"] = "STREAM"
            response["X-Total-Count"] = str(count)
            response["X-Data-Version"] = data_version
            # Allow CORS to read custom headers
            response["Access-Control-Expose-Headers"] = (
                "X-Total-Count, X-Cache-Status, X-Data-Version"
            )
            return response

        # Small dataset - serialize normally and cache
        serializer_class = getattr(
            self, "get_geojson_serializer_class", self.get_serializer_class
        )
        serializer = serializer_class()(
            queryset, many=True, context={"request": request}
        )
        data = serializer.data

        # Cache the result if no bbox filter
        if not bbox:
            cache_key = self.get_cache_key(request)
            timeout = getattr(self, "cache_timeout", None)
            cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
            caches[cache_alias].set(cache_key, data, timeout=timeout)

        response = Response(data)
        response["X-Cache-Status"] = "MISS"
        response["X-Total-Count"] = str(count)
        # Use cache_key if available for version, otherwise generate one
        version_key = data_version
        response["X-Data-Version"] = version_key
        response["Access-Control-Expose-Headers"] = (
            "X-Total-Count, X-Cache-Status, X-Data-Version"
        )
        return response

    def get_geojson_serializer_class(self):
        """
        ViewSets using this mixin should implement this method to specify
        the serializer used specifically for the GeoJSON action.
        Falls back to get_serializer_class if not defined.
        """
        return self.get_serializer_class()


class GeoJSONMixin:
    """
    Mixin to add GeoJSON endpoint to a viewset.

    To use this mixin, the viewset must:
    1. Define a `geojson_serializer_class` attribute or override get_geojson_serializer_class()
    2. Be used with a viewset that handles permissions and filtering via get_queryset()

    The GeoJSON endpoint relies on the viewset's get_queryset() method to handle
    permission-based filtering, and supports a `scope` parameter to determine
    which objects to include.
    """

    geojson_serializer_class = None

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        """
        Return GeoJSON data with scope-based filtering.

        Relies on the viewset's get_queryset() method to handle filtering.
        The viewset should check for the 'geojson' action and handle the scope parameter.
        """
        # Get base queryset - the parent viewset should handle filtering based on scope
        queryset = self.get_queryset()

        # Apply standard filtering (search, ordering, etc.)
        queryset = self.filter_queryset(queryset)

        serializer = self.get_geojson_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_geojson_serializer(self, *args, **kwargs):
        """
        Return the GeoJSON serializer instance.
        """
        serializer_class = self.get_geojson_serializer_class()
        kwargs.setdefault("context", self.get_geojson_serializer_context())
        return serializer_class(*args, **kwargs)

    def get_geojson_serializer_context(self):
        """
        Return the context to use for the GeoJSON serializer.
        Defaults to using the serializer context from the parent viewset.
        """
        return self.get_serializer_context()

    def get_geojson_serializer_class(self):
        """
        Return the class to use for the GeoJSON serializer.
        Defaults to using `geojson_serializer_class` attribute.
        """
        assert self.geojson_serializer_class is not None, (
            f"'{self.__class__.__name__}' should either include a `geojson_serializer_class` attribute, "
            "or override the `get_geojson_serializer_class()` method."
        )
        return self.geojson_serializer_class
