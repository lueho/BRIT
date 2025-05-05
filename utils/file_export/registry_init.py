from utils.file_export.export_registry import register_export
from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.serializers import CollectionFlatSerializer
from case_studies.soilcom.renderers import CollectionXLSXRenderer, CollectionCSVRenderer
from case_studies.soilcom.models import Collection

register_export(
    'soilcom.Collection',
    CollectionFilterSet,
    CollectionFlatSerializer,
    {'xlsx': CollectionXLSXRenderer, 'csv': CollectionCSVRenderer}
)

from case_studies.flexibi_hamburg.filters import HamburgRoadsideTreesFilterSet
from case_studies.flexibi_hamburg.serializers import HamburgRoadsideTreeFlatSerializer
from case_studies.flexibi_hamburg.renderers import HamburgRoadsideTreesXLSXRenderer, HamburgRoadsideTreesCSVRenderer
from case_studies.flexibi_hamburg.models import HamburgRoadsideTrees

register_export(
    'flexibi_hamburg.HamburgRoadsideTrees',
    HamburgRoadsideTreesFilterSet,
    HamburgRoadsideTreeFlatSerializer,
    {'xlsx': HamburgRoadsideTreesXLSXRenderer, 'csv': HamburgRoadsideTreesCSVRenderer}
)

from case_studies.flexibi_nantes.filters import NantesGreenhousesFilterSet
from case_studies.flexibi_nantes.serializers import NantesGreenhousesFlatSerializer
from case_studies.flexibi_nantes.renderers import NantesGreenhousesXLSXRenderer, NantesGreenhousesCSVRenderer

register_export(
    'flexibi_nantes.NantesGreenhouses',
    NantesGreenhousesFilterSet,
    NantesGreenhousesFlatSerializer,
    {'xlsx': NantesGreenhousesXLSXRenderer, 'csv': NantesGreenhousesCSVRenderer}
)
