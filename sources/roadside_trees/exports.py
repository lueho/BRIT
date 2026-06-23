from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
from sources.roadside_trees.renderers import (
    HamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesXLSXRenderer,
)
from sources.roadside_trees.serializers import HamburgRoadsideTreeFlatSerializer
from utils.file_export.contracts import SourceDomainExport
from utils.file_export.export_registry import register_export

EXPORTS = (
    SourceDomainExport(
        model_label="roadside_trees.HamburgRoadsideTrees",
        filterset=HamburgRoadsideTreesFilterSet,
        serializer=HamburgRoadsideTreeFlatSerializer,
        renderers={
            "xlsx": HamburgRoadsideTreesXLSXRenderer,
            "csv": HamburgRoadsideTreesCSVRenderer,
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
    "HamburgRoadsideTreesCSVRenderer",
    "HamburgRoadsideTreesFilterSet",
    "HamburgRoadsideTreeFlatSerializer",
    "HamburgRoadsideTreesXLSXRenderer",
    "register_exports",
]
