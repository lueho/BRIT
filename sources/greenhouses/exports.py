from sources.contracts import SourceDomainExport
from sources.greenhouses.filters import NantesGreenhousesFilterSet
from sources.greenhouses.renderers import (
    NantesGreenhousesCSVRenderer,
    NantesGreenhousesXLSXRenderer,
)
from sources.greenhouses.serializers import NantesGreenhousesFlatSerializer

EXPORTS = (
    SourceDomainExport(
        model_label="greenhouses.NantesGreenhouses",
        filterset=NantesGreenhousesFilterSet,
        serializer=NantesGreenhousesFlatSerializer,
        renderers={
            "xlsx": NantesGreenhousesXLSXRenderer,
            "csv": NantesGreenhousesCSVRenderer,
        },
    ),
)

__all__ = [
    "EXPORTS",
    "NantesGreenhousesCSVRenderer",
    "NantesGreenhousesFilterSet",
    "NantesGreenhousesFlatSerializer",
    "NantesGreenhousesXLSXRenderer",
]
