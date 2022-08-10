from django.http.request import QueryDict, MultiValueDict

from brit.celery import app
import brit.storages

from .filters import CollectionFilter
from .models import Collection
from .renderers import CollectionXLSXRenderer, CollectionCSVRenderer
from .serializers import CollectionFlatSerializer


@app.task(bind=True)
def export_collections_to_file(self, file_format, query_params):
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))

    qs = CollectionFilter(qdict, Collection.objects.all()).qs
    data = CollectionFlatSerializer(qs, many=True).data

    file_name = f'collections_{self.request.id}.{file_format}'
    if file_format == 'xlsx':
        return brit.storages.write_file_for_download(file_name, data, CollectionXLSXRenderer)
    else:
        return brit.storages.write_file_for_download(file_name, data, CollectionCSVRenderer)
