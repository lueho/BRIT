from django.http.request import QueryDict, MultiValueDict

from brit.celery import app
from brit.storages import TemporaryUserCollectionFileStorage

from .models import Collection
from .renderers import CollectionXLSXRenderer
from .serializers import CollectionFlatSerializer
from .filters import CollectionFilter


@app.task(bind=True)
def export_collections_to_xlsx(self, query_params):

    # The query parameter dictionary needs to be deserialized in order to work correctly
    query_params.pop('page', None)
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))

    qs = CollectionFilter(qdict, Collection.objects.all()).qs
    serializer = CollectionFlatSerializer(qs, many=True)

    file_name = f'collections_{self.request.id}.xlsx'
    storage = TemporaryUserCollectionFileStorage()
    renderer = CollectionXLSXRenderer()

    with storage.open(file_name, 'w') as file:
        renderer.render(file, serializer.data)

    return storage.url(file_name)
