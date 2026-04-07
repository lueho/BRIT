from sources.greenhouses.exports import (
    NantesGreenhousesCSVRenderer,
    NantesGreenhousesFilterSet,
    NantesGreenhousesFlatSerializer,
    NantesGreenhousesXLSXRenderer,
)
from sources.roadside_trees.exports import (
    HamburgRoadsideTreeFlatSerializer,
    HamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesFilterSet,
    HamburgRoadsideTreesXLSXRenderer,
)
from sources.waste_collection.exports import (
    CollectionCSVRenderer,
    CollectionFilterSet,
    CollectionFlatSerializer,
    CollectionXLSXRenderer,
)
from utils.file_export.export_registry import register_export

register_export(
    "waste_collection.Collection",
    CollectionFilterSet,
    CollectionFlatSerializer,
    {"xlsx": CollectionXLSXRenderer, "csv": CollectionCSVRenderer},
)

register_export(
    "roadside_trees.HamburgRoadsideTrees",
    HamburgRoadsideTreesFilterSet,
    HamburgRoadsideTreeFlatSerializer,
    {"xlsx": HamburgRoadsideTreesXLSXRenderer, "csv": HamburgRoadsideTreesCSVRenderer},
)

register_export(
    "greenhouses.NantesGreenhouses",
    NantesGreenhousesFilterSet,
    NantesGreenhousesFlatSerializer,
    {"xlsx": NantesGreenhousesXLSXRenderer, "csv": NantesGreenhousesCSVRenderer},
)
