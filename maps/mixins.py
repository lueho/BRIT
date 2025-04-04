from django.conf import settings
from rest_framework.decorators import action
from rest_framework.response import Response

from .utils import get_or_set_cache


class CachedGeoJSONMixin:
    """
    Mixin to add caching to GeoJSON endpoints using the get_or_set_cache helper.
    Requires the ViewSet to implement `get_cache_key(self, request)`
    and `get_geojson_serializer_class(self)`.
    """

    # Default cache timeout for this mixin - can be overridden in ViewSet
    cache_timeout = getattr(settings, 'CACHES', {}).get(
        getattr(settings, 'GEOJSON_CACHE', 'default'), {}).get('TIMEOUT', 3600)  # Default 1 hour fallback

    def get_geojson_data(self):
        """Generates the GeoJSON data. Expected to be called on cache miss."""
        queryset = self.filter_queryset(self.get_queryset())
        # Ensure ViewSet implements get_geojson_serializer_class or adapt as needed
        serializer_class = getattr(self, 'get_geojson_serializer_class', self.get_serializer_class)
        serializer = serializer_class()(queryset, many=True, context={'request': self.request})
        return serializer.data

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        # Ensure ViewSet implements get_cache_key or adapt as needed
        if not hasattr(self, 'get_cache_key'):
            raise NotImplementedError("ViewSet must implement get_cache_key when using CachedGeoJSONMixin")

        cache_key = self.get_cache_key(request)
        timeout = getattr(self, 'cache_timeout', None)  # Allow override per ViewSet

        data, cache_hit = get_or_set_cache(cache_key, self.get_geojson_data, timeout=timeout)

        response = Response(data)
        response['X-Cache-Status'] = "HIT" if cache_hit else "MISS"
        return response

    def get_geojson_serializer_class(self):
        """
        ViewSets using this mixin should implement this method to specify
        the serializer used specifically for the GeoJSON action.
        Falls back to get_serializer_class if not defined.
        """
        return self.get_serializer_class()
