"""GeoJSON adapter module for waste_collection sources."""

from django.db.models import Exists, OuterRef

from sources.waste_collection.models import Collection
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    WasteCollectionGeometrySerializer,
)


def exclude_published_predecessors(queryset):
    """Keep rows without a published successor, as the default map does."""
    published_successors = Collection.objects.filter(
        publication_status=Collection.STATUS_PUBLISHED,
        predecessors=OuterRef("pk"),
    )
    return queryset.annotate(has_visible_successor=Exists(published_successors)).filter(
        has_visible_successor=False
    )


__all__ = [
    "Collection",
    "GEOMETRY_SIMPLIFY_TOLERANCE",
    "WasteCollectionGeometrySerializer",
    "exclude_published_predecessors",
]
