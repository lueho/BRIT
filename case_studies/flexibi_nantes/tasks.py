from django.http.request import QueryDict, MultiValueDict

from brit.celery import app
import utils.file_export.storages

from .filters import NantesGreenhousesFilterSet
from .models import NantesGreenhouses
from .renderers import NantesGreenhousesXLSXRenderer, NantesGreenhousesCSVRenderer
from .serializers import NantesGreenhousesFlatSerializer


@app.task(bind=True)
def export_nantes_greenhouses_to_file(self, file_format, query_params):
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))

    qs = NantesGreenhousesFilterSet(qdict, NantesGreenhouses.objects.all()).qs
    data = NantesGreenhousesFlatSerializer(qs, many=True).data

    file_name = f'nantes_greenhouses_{self.request.id}.{file_format}'
    if file_format == 'xlsx':
        return utils.file_export.storages.write_file_for_download(file_name, data, NantesGreenhousesXLSXRenderer)
    else:
        return utils.file_export.storages.write_file_for_download(file_name, data, NantesGreenhousesCSVRenderer)