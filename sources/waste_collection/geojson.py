"""GeoJSON adapter module for waste_collection sources."""

from sources.waste_collection.models import Collection
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    WasteCollectionGeometrySerializer,
)

__all__ = [
    "Collection",
    "GEOMETRY_SIMPLIFY_TOLERANCE",
    "WasteCollectionGeometrySerializer",
]
