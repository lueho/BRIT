from sources.contracts import SourceDomainExport
from sources.waste_collection.filters import CollectionFilterSet
from sources.waste_collection.renderers import (
    CollectionCSVRenderer,
    CollectionXLSXRenderer,
)
from sources.waste_collection.serializers import CollectionFlatSerializer

EXPORTS = (
    SourceDomainExport(
        model_label="waste_collection.Collection",
        filterset=CollectionFilterSet,
        serializer=CollectionFlatSerializer,
        renderers={
            "xlsx": CollectionXLSXRenderer,
            "csv": CollectionCSVRenderer,
        },
    ),
)

__all__ = [
    "EXPORTS",
    "CollectionCSVRenderer",
    "CollectionFilterSet",
    "CollectionFlatSerializer",
    "CollectionXLSXRenderer",
]
