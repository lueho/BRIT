"""Celery tasks for review-workflow notifications."""

import logging
import smtplib

from celery import shared_task
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="utils.object_management.send_review_action_owner_notification",
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_review_action_owner_notification(self, review_action_id, recipient_id=None):
    """Notify the object owner about a review action performed by someone else.

    ``recipient_id`` identifies the user who owned the object when the
    action was created, captured by the post-save signal so that an
    ownership transfer between enqueue and delivery does not redirect the
    notification. Missing actions and recipients are terminal skips;
    transient mail delivery failures are retried with backoff.
    """
    from .models import ReviewAction
    from .notifications import notify_owner_of_review_action

    try:
        action = ReviewAction.objects.select_related("user").get(pk=review_action_id)
    except ReviewAction.DoesNotExist:
        logger.warning(
            "ReviewAction %s no longer exists; skipping owner notification.",
            review_action_id,
        )
        return False
    recipient = None
    if recipient_id is not None:
        try:
            recipient = User.objects.get(pk=recipient_id)
        except User.DoesNotExist:
            logger.warning(
                "Recipient %s for ReviewAction %s no longer exists; "
                "skipping owner notification.",
                recipient_id,
                review_action_id,
            )
            return False
    return notify_owner_of_review_action(action, recipient=recipient)
