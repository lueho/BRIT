from celery import shared_task
from django.http.request import QueryDict, MultiValueDict
from utils.file_export.export_registry import get_export_spec
import utils.file_export.storages

@shared_task(bind=True)
def brit_export_user_created_object_to_file(self, model_label, file_format, query_params, context):
    """
    BRIT-specific wrapper for export_user_created_object_to_file.
    Applies owner/publication_status/list_type filtering as required by BRIT logic.
    """
    spec = get_export_spec(model_label)
    qdict = QueryDict("", mutable=True)
    qdict.update(MultiValueDict(query_params))
    user_id = context.get("user_id")
    list_type = context.get("list_type", "public")
    if list_type == "private":
        base_qs = spec.model.objects.filter(owner_id=user_id)
    else:
        if "publication_status" in [f.name for f in spec.model._meta.get_fields()]:
            base_qs = spec.model.objects.filter(publication_status="published")
        else:
            base_qs = spec.model.objects.all()
    qs = spec.filterset(qdict, queryset=base_qs).qs
    data = spec.serializer(qs, many=True).data
    renderer = spec.renderers[file_format]
    file_name = f"{spec.model._meta.model_name}_{self.request.id}.{file_format}"
    return utils.file_export.storages.write_file_for_download(file_name, data, renderer)
