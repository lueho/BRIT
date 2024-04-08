from django.http.request import QueryDict, MultiValueDict

from brit.celery import app
import utils.file_export.storages

from .filters import HamburgRoadsideTreesFilterSet
from .models import HamburgRoadsideTrees
from .renderers import HamburgRoadsideTreesXLSXRenderer, HamburgRoadsideTreesCSVRenderer
from .serializers import HamburgRoadsideTreeFlatSerializer


@app.task(bind=True)
def export_hamburg_roadside_trees_to_file(self, file_format, query_params):
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))

    qs = HamburgRoadsideTreesFilterSet(qdict, HamburgRoadsideTrees.objects.all()).qs
    data = HamburgRoadsideTreeFlatSerializer(qs, many=True).data

    file_name = f'hamburg_roadside_trees_{self.request.id}.{file_format}'
    if file_format == 'xlsx':
        return utils.file_export.storages.write_file_for_download(file_name, data, HamburgRoadsideTreesXLSXRenderer)
    else:
        return utils.file_export.storages.write_file_for_download(file_name, data, HamburgRoadsideTreesCSVRenderer)