"""Celery tasks for review-workflow notifications."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="utils.object_management.send_review_action_owner_notification")
def send_review_action_owner_notification(review_action_id):
    """Notify the object owner about a review action performed by someone else."""
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
    return notify_owner_of_review_action(action)
