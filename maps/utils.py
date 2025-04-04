from django.conf import settings
from django.core.cache import caches
import hashlib
import json

def _generate_filter_key_part(filters=None):
    """Helper to generate a deterministic string from filter parameters."""
    if not filters:
        return "all"
    # Sort dict items for consistency, convert values to strings, handle potential complex types safely
    # Using json.dumps ensures consistent representation for nested structures/various types if needed,
    # though simple key:value pairs are assumed here. Use sort_keys for added determinism.
    # Using hashlib ensures fixed length and avoids overly long keys if filters get complex.
    filter_string = json.dumps(dict(sorted(filters.items())), sort_keys=True)
    return hashlib.sha1(filter_string.encode('utf-8')).hexdigest()[:16] # Short hash

def get_location_cache_key(location_id=None, filters=None):
    """Generate a cache key for Location GeoJSON data."""
    if location_id:
        # Usually GeoJSON would be for collections, but handle single ID if needed
        key = f"location_geojson:id:{location_id}"
    else:
        filter_part = _generate_filter_key_part(filters)
        key = f"location_geojson:filter:{filter_part}"
    return key

def get_region_cache_key(region_id=None, filters=None):
    """Generate a cache key for Region GeoJSON data."""
    if region_id:
        key = f"region_geojson:id:{region_id}"
    else:
        # Remove 'id' from filters if present, as it's handled above
        filters_copy = filters.copy() if filters else {}
        filters_copy.pop('id', None)
        filter_part = _generate_filter_key_part(filters_copy)
        key = f"region_geojson:filter:{filter_part}"
    return key

def get_catchment_cache_key(catchment_id=None, filters=None):
    """Generate a cache key for Catchment GeoJSON data."""
    if catchment_id:
        key = f"catchment_geojson:id:{catchment_id}"
    else:
        filters_copy = filters.copy() if filters else {}
        filters_copy.pop('id', None)
        filter_part = _generate_filter_key_part(filters_copy)
        key = f"catchment_geojson:filter:{filter_part}"
    return key

def get_nuts_region_cache_key(level=None, parent_id=None, nuts_id=None, filters=None):
    """Generate a cache key for NUTS region GeoJSON data."""
    # Prioritize specific NUTS ID if provided
    if nuts_id:
         return f"nuts_geojson:id:{nuts_id}"

    parts = ["nuts_geojson"]
    if level is not None:
        parts.append(f"level:{level}")
    if parent_id is not None:
        parts.append(f"parent:{parent_id}")

    # Filter part generation based on remaining filters
    filters_copy = filters.copy() if filters else {}
    filters_copy.pop('levl_code', None) # Already handled by 'level' parameter
    filters_copy.pop('parent_id', None) # Already handled by 'parent_id' parameter
    filters_copy.pop('id', None) # Already handled by 'nuts_id' parameter

    if filters_copy:
         filter_part = _generate_filter_key_part(filters_copy)
         parts.append(f"filter:{filter_part}")
    elif len(parts) == 1: # Only "nuts_geojson"
         parts.append("all") # Indicate fetching all NUTS regions if no level/parent/filter

    return ":".join(parts)

def get_or_set_cache(cache_key, data_generator_func, timeout=None):
    """
    Helper function to abstract the cache get/set pattern.
    Args:
        cache_key (str): The key to use for caching.
        data_generator_func (callable): A function that generates the data if not found in cache.
        timeout (int, optional): Specific timeout for this cache entry. Defaults to cache's default.
    Returns:
        The cached data or newly generated data.
        bool: True if data was retrieved from cache, False otherwise.
    """
    cache_alias = getattr(settings, 'GEOJSON_CACHE', 'default')
    cache = caches[cache_alias]
    cached_data = cache.get(cache_key)

    if cached_data is not None:
        return cached_data, True # Data from cache, Hit=True

    # Cache miss, generate data
    new_data = data_generator_func()

    # Cache the newly generated data
    cache.set(cache_key, new_data, timeout=timeout)

    return new_data, False # Newly generated data, Hit=False