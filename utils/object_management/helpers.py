import logging

from django.contrib.contenttypes.models import ContentType

from .models import ReviewAction

logger = logging.getLogger(__name__)


def create_review_action(obj, user, action, comment=""):
    return ReviewAction.objects.create(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
        user=user,
        action=action,
        comment=comment,
    )


def create_review_action_safely(obj, user, action, comment="", exceptions=Exception):
    """Create a ReviewAction, logging and swallowing the given exception types."""
    try:
        return create_review_action(obj, user, action, comment)
    except exceptions as exc:
        logger.warning("Failed to create ReviewAction for %s: %s", action, exc)
        return None


def invoke_cascade_handler(
    obj, action_name, actor, previous_status=None, exceptions=Exception
):
    """Invoke obj.cascade_review_action if the model provides one."""
    cascade_handler = getattr(obj, "cascade_review_action", None)
    if not callable(cascade_handler):
        return

    try:
        cascade_handler(
            action_name=action_name,
            actor=actor,
            previous_status=previous_status,
        )
    except exceptions as exc:
        logger.warning("Review action cascade failed for %s: %s", obj, exc)
