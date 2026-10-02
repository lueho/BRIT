"""E-mail notifications for the review workflow."""

import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import capfirst

from .models import ReviewAction

logger = logging.getLogger(__name__)

SUBJECT_TEMPLATE = "object_management/emails/review_owner_notification_subject.txt"
BODY_TEMPLATE = "object_management/emails/review_owner_notification_body.txt"

ACTION_SUMMARIES = {
    ReviewAction.ACTION_SUBMITTED: "was submitted for review",
    ReviewAction.ACTION_APPROVED: "was approved and is now published",
    ReviewAction.ACTION_REJECTED: "was declined during review",
    ReviewAction.ACTION_WITHDRAWN: "was withdrawn from review",
    ReviewAction.ACTION_COMMENT: "received new review feedback",
}


def _from_email():
    return settings.DEFAULT_FROM_EMAIL or settings.SERVER_EMAIL


def notify_owner_of_review_action(action):
    """Send a notification e-mail to the object owner for a review action.

    Only actions performed by someone other than the owner trigger an
    e-mail. Returns True when an e-mail was sent.
    """
    obj = action.content_object
    owner = getattr(obj, "owner", None) if obj is not None else None
    if owner is None or owner.pk == action.user_id or not owner.email:
        return False

    context = {
        "action": action,
        "actor": action.user,
        "object": obj,
        "object_name": getattr(obj, "name", None) or str(obj),
        "object_verbose_name": capfirst(obj._meta.verbose_name),
        "summary": ACTION_SUMMARIES.get(action.action, "was updated during review"),
        "site": Site.objects.get_current(),
        "review_url": reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": action.content_type_id,
                "object_id": action.object_id,
            },
        ),
    }
    subject = render_to_string(SUBJECT_TEMPLATE, context).strip()
    body = render_to_string(BODY_TEMPLATE, context)
    send_mail(
        subject,
        body,
        _from_email(),
        [owner.email],
    )
    logger.info(
        "Sent review notification for %s %s (action=%s) to %s",
        action.content_type.model,
        action.object_id,
        action.action,
        owner.email,
    )
    return True
