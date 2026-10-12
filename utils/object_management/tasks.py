"""Celery tasks for review-workflow notifications."""

import logging
import smtplib

from celery import shared_task
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="utils.object_management.send_review_action_notifications",
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_review_action_notifications(self, review_action_id, owner_id=None):
    """Notify the owner and past commenters about a review action.

    ``owner_id`` identifies the user who owned the object when the action
    was created, captured by the post-save signal so that an ownership
    transfer between enqueue and delivery does not redirect the
    notification. Missing actions are terminal skips; transient mail
    delivery failures are retried with backoff.
    """
    from .models import ReviewAction
    from .notifications import notify_review_participants

    try:
        action = ReviewAction.objects.select_related("user").get(pk=review_action_id)
    except ReviewAction.DoesNotExist:
        logger.warning(
            "ReviewAction %s no longer exists; skipping notifications.",
            review_action_id,
        )
        return 0
    owner = None
    if owner_id is not None:
        try:
            owner = User.objects.get(pk=owner_id)
        except User.DoesNotExist:
            logger.warning(
                "Owner %s for ReviewAction %s no longer exists; "
                "notifying past commenters only.",
                owner_id,
                review_action_id,
            )
    return notify_review_participants(action, owner=owner)
