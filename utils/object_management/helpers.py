from django.contrib.contenttypes.models import ContentType

from .models import ReviewAction


def create_review_action(
    obj,
    user,
    action,
    comment="",
    *,
    content_revision=None,
    changed_fields=None,
):
    return ReviewAction.objects.create(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
        user=user,
        action=action,
        comment=comment,
        content_revision=content_revision,
        changed_fields=list(changed_fields or []),
    )
