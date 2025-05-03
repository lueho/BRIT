from django.http.request import QueryDict, MultiValueDict
from django.apps import apps
from celery import shared_task
import utils.file_export.storages
from .export_registry import get_export_spec
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def export_user_created_object_to_file(self, model_label, file_format, query_params, allowed_ids):
    spec = get_export_spec(model_label)
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))
    base_qs = spec.model.objects.filter(pk__in=allowed_ids)
    qs = spec.filterset(qdict, queryset=base_qs).qs
    data = spec.serializer(qs, many=True).data
    renderer = spec.renderers[file_format]
    file_name = f'{spec.model._meta.model_name}_{self.request.id}.{file_format}'
    return utils.file_export.storages.write_file_for_download(file_name, data, renderer)
