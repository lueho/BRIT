from case_studies.flexibi_hamburg.filters import HamburgRoadsideTreesFilterSet
from case_studies.flexibi_hamburg.renderers import (
    HamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesXLSXRenderer,
)
from case_studies.flexibi_hamburg.serializers import HamburgRoadsideTreeFlatSerializer
from case_studies.flexibi_nantes.filters import NantesGreenhousesFilterSet
from case_studies.flexibi_nantes.renderers import (
    NantesGreenhousesCSVRenderer,
    NantesGreenhousesXLSXRenderer,
)
from case_studies.flexibi_nantes.serializers import NantesGreenhousesFlatSerializer
from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.renderers import CollectionCSVRenderer, CollectionXLSXRenderer
from case_studies.soilcom.serializers import CollectionFlatSerializer
from utils.file_export.export_registry import register_export

register_export(
    "soilcom.Collection",
    CollectionFilterSet,
    CollectionFlatSerializer,
    {"xlsx": CollectionXLSXRenderer, "csv": CollectionCSVRenderer},
)

register_export(
    "flexibi_hamburg.HamburgRoadsideTrees",
    HamburgRoadsideTreesFilterSet,
    HamburgRoadsideTreeFlatSerializer,
    {"xlsx": HamburgRoadsideTreesXLSXRenderer, "csv": HamburgRoadsideTreesCSVRenderer},
)

register_export(
    "flexibi_nantes.NantesGreenhouses",
    NantesGreenhousesFilterSet,
    NantesGreenhousesFlatSerializer,
    {"xlsx": NantesGreenhousesXLSXRenderer, "csv": NantesGreenhousesCSVRenderer},
)
