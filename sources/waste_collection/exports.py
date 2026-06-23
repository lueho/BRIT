from sources.waste_collection.filters import CollectionFilterSet
from sources.waste_collection.renderers import (
    CollectionCSVRenderer,
    CollectionXLSXRenderer,
)
from sources.waste_collection.serializers import CollectionFlatSerializer
from utils.file_export.contracts import SourceDomainExport
from utils.file_export.export_registry import register_export

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


def register_exports():
    for export in EXPORTS:
        register_export(
            export.model_label,
            export.filterset,
            export.serializer,
            export.renderers,
        )


__all__ = [
    "EXPORTS",
    "CollectionCSVRenderer",
    "CollectionFilterSet",
    "CollectionFlatSerializer",
    "CollectionXLSXRenderer",
    "register_exports",
]
