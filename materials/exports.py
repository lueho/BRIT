from materials.filters import SampleFilter
from materials.renderers import SampleCSVRenderer, SampleXLSXRenderer
from materials.serializers import SampleFlatSerializer
from utils.file_export.export_registry import register_export

register_export(
    "materials.Sample",
    SampleFilter,
    SampleFlatSerializer,
    {
        "csv": SampleCSVRenderer(),
        "xlsx": SampleXLSXRenderer(),
    },
)
