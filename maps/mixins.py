import json

from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.http import StreamingHttpResponse
from rest_framework.decorators import action
from rest_framework.response import Response

from .utils import get_or_set_cache

# Threshold for switching to streaming response (number of features)
STREAMING_THRESHOLD = 100

# Enable streaming for large uncached requests
STREAMING_ENABLED = True


class CachedGeoJSONMixin:
    """
    Mixin to add caching to GeoJSON endpoints using the get_or_set_cache helper.
    Requires the ViewSet to implement `get_cache_key(self, request)`
    and `get_geojson_serializer_class(self)`.

    Supports optional bounding box filtering via `bbox` query parameter.
    For large datasets, uses streaming response to reduce memory pressure.
    """

    # Default cache timeout for this mixin - can be overridden in ViewSet
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

        bbox = self._parse_bbox(request)
        if bbox:
            queryset = self._apply_bbox_filter(queryset, bbox)
        return queryset

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

        # Try cache first (unless streaming is explicitly requested)
        if not use_stream and not bbox:
            cache_key = self.get_cache_key(request)
            timeout = getattr(self, "cache_timeout", None)

            data, cache_hit = get_or_set_cache(
                cache_key, self.get_geojson_data, timeout=timeout
            )

            if cache_hit:
                response = Response(data)
                response["X-Cache-Status"] = "HIT"
                # Add feature count for frontend progress
                if isinstance(data, dict) and "features" in data:
                    response["X-Total-Count"] = str(len(data["features"]))
                return response

        # Cache miss or streaming requested - get queryset
        queryset = self.get_geojson_queryset_with_bbox(request)
        count = queryset.count()

        # Use streaming for large datasets to prevent memory issues
        if STREAMING_ENABLED and count > STREAMING_THRESHOLD:
            response = StreamingHttpResponse(
                self._stream_geojson(queryset),
                content_type="application/geo+json",
            )
            response["X-Cache-Status"] = "STREAM"
            response["X-Total-Count"] = str(count)
            # Allow CORS to read custom headers
            response["Access-Control-Expose-Headers"] = "X-Total-Count, X-Cache-Status"
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
            from django.core.cache import caches

            cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
            caches[cache_alias].set(cache_key, data, timeout=timeout)

        response = Response(data)
        response["X-Cache-Status"] = "MISS"
        response["X-Total-Count"] = str(count)
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
