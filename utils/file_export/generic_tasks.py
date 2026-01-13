from celery import shared_task
from django.http.request import MultiValueDict, QueryDict

import utils.file_export.storages

from .export_registry import get_export_spec

BATCH_SIZE = 50


@shared_task(bind=True)
def export_user_created_object_to_file(
    self, model_label, file_format, query_params, context
):
    """
    Export user-created objects to a file with progress reporting.

    Reports progress during serialization so the frontend can display
    a progress bar based on the number of records processed.
    """
    spec = get_export_spec(model_label)
    qdict = QueryDict("", mutable=True)
    qdict.update(MultiValueDict(query_params))

    # Build base queryset using context (user_id, list_type)
    user_id = context.get("user_id")
    list_type = context.get("list_type", "public")
    if list_type == "private":
        base_qs = spec.model.objects.filter(owner_id=user_id)
    else:
        # Only filter by publication_status if the field exists
        if "publication_status" in [f.name for f in spec.model._meta.get_fields()]:
            base_qs = spec.model.objects.filter(publication_status="published")
        else:
            base_qs = spec.model.objects.all()

    qs = spec.filterset(qdict, queryset=base_qs).qs
    total = qs.count()

    # Report initial state
    self.update_state(
        state="PROGRESS",
        meta={"current": 0, "total": total, "percent": 0},
    )

    # Serialize in batches with progress reporting
    data = []
    for i in range(0, total, BATCH_SIZE):
        batch = list(qs[i : i + BATCH_SIZE])
        batch_data = spec.serializer(batch, many=True).data
        data.extend(batch_data)

        current = min(i + BATCH_SIZE, total)
        percent = int((current / total) * 100) if total > 0 else 100
        self.update_state(
            state="PROGRESS",
            meta={"current": current, "total": total, "percent": percent},
        )

    renderer = spec.renderers[file_format]
    file_name = f"{spec.model._meta.model_name}_{self.request.id}.{file_format}"
    return utils.file_export.storages.write_file_for_download(file_name, data, renderer)
