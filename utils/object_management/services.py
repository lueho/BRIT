from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from .models import ReviewAction
from .registry import model_policy


def _facet_models(model):
    models = {model}
    models.update(model._meta.get_parent_list())
    for candidate in apps.get_models():
        if model in candidate._meta.get_parent_list():
            models.add(candidate)
    return {m for m in models if model_policy(m) is not None}


def _facet_content_types(model):
    return [ContentType.objects.get_for_model(facet) for facet in _facet_models(model)]


def _review_actions_for_root(root):
    return ReviewAction.objects.filter(
        content_type__in=_facet_content_types(type(root)), object_id=root.pk
    )


def contributor_user_ids(root):
    """Users who created or meaningfully edited this root's current candidate."""
    return set(
        _review_actions_for_root(root)
        .filter(
            action__in=(
                ReviewAction.ACTION_CREATED,
                ReviewAction.ACTION_EDITED,
            )
        )
        .values_list("user_id", flat=True)
    )
