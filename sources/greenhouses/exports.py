from sources.greenhouses.filters import NantesGreenhousesFilterSet
from sources.greenhouses.renderers import (
    NantesGreenhousesCSVRenderer,
    NantesGreenhousesXLSXRenderer,
)
from sources.greenhouses.serializers import NantesGreenhousesFlatSerializer
from utils.file_export.contracts import SourceDomainExport
from utils.file_export.export_registry import register_export

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
    "NantesGreenhousesCSVRenderer",
    "NantesGreenhousesFilterSet",
    "NantesGreenhousesFlatSerializer",
    "NantesGreenhousesXLSXRenderer",
    "register_exports",
]
