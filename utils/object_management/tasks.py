"""Celery tasks for review-workflow notifications."""

import logging
import smtplib

from celery import shared_task
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@shared_task(name="utils.object_management.send_review_action_notifications")
def send_review_action_notifications(review_action_id, owner_id=None):
    """Fan out notifications for a review action, one task per recipient.

    ``owner_id`` identifies the user who owned the object when the action
    was created, captured by the post-save signal so that an ownership
    transfer between enqueue and delivery does not redirect the
    notification. Each recipient gets an independently retried delivery
    task, so a transient mail failure for one recipient never resends to
    the others. Returns the number of queued deliveries.
    """
    from .models import ReviewAction
    from .notifications import review_notification_recipients

    try:
        action = ReviewAction.objects.get(pk=review_action_id)
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
    recipients = review_notification_recipients(action, owner=owner)
    for recipient in recipients:
        send_review_action_notification_to_user.delay(review_action_id, recipient.pk)
    return len(recipients)


@shared_task(
    name="utils.object_management.send_review_action_notification_to_user",
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_review_action_notification_to_user(review_action_id, recipient_id):
    """Deliver one review notification e-mail; transient failures are retried.

    Missing actions or recipients are terminal skips. Eligibility (actor,
    e-mail address, review-page access) is re-checked at delivery time.
    """
    from .models import ReviewAction
    from .notifications import send_review_action_notification

    try:
        action = ReviewAction.objects.select_related("user").get(pk=review_action_id)
        recipient = User.objects.get(pk=recipient_id)
    except (ReviewAction.DoesNotExist, User.DoesNotExist):
        logger.warning(
            "ReviewAction %s or recipient %s no longer exists; skipping notification.",
            review_action_id,
            recipient_id,
        )
        return False
    return send_review_action_notification(action, recipient)
