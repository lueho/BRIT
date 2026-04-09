from sources.contracts import SourceDomainExport
from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
from sources.roadside_trees.renderers import (
    HamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesXLSXRenderer,
)
from sources.roadside_trees.serializers import HamburgRoadsideTreeFlatSerializer

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

__all__ = [
    "EXPORTS",
    "HamburgRoadsideTreesCSVRenderer",
    "HamburgRoadsideTreesFilterSet",
    "HamburgRoadsideTreeFlatSerializer",
    "HamburgRoadsideTreesXLSXRenderer",
]
