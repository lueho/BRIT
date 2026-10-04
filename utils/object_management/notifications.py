"""E-mail notifications for the review workflow."""

import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import capfirst

from .models import ReviewAction
from .permissions import user_is_moderator_for_model

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


def _notification_site():
    """Return the Site used for links in notification e-mails.

    A fresh deployment may lack the Site row referenced by SITE_ID
    (production uses SITE_ID=2 while Django's migrations only create
    site 1), so fall back to the configured canonical host instead of
    failing the notification.
    """
    try:
        return Site.objects.get_current()
    except Site.DoesNotExist:
        domain = getattr(settings, "CANONICAL_HOST", "") or next(
            (
                host.lstrip(".")
                for host in settings.ALLOWED_HOSTS
                if host not in ("*", "")
            ),
            "",
        )
        logger.warning(
            "No Site row for SITE_ID=%s; falling back to domain %r for "
            "notification links.",
            getattr(settings, "SITE_ID", None),
            domain,
        )
        return Site(domain=domain, name=domain)


def _notification_protocol():
    """URL scheme for notification links; production enforces HTTPS."""
    return "https" if getattr(settings, "SECURE_SSL_REDIRECT", False) else "http"


def _can_open_review_link(user, obj):
    """Mirror ``ReviewItemDetailView`` access: current owner or moderator."""
    return user.pk == obj.owner_id or user_is_moderator_for_model(user, obj.__class__)


def notify_owner_of_review_action(action, recipient=None):
    """Send a notification e-mail to the object owner for a review action.

    ``recipient`` is the user who owned the object when the action was
    created; the post-save signal captures it so an ownership transfer
    between enqueue and delivery does not redirect the notification. When
    omitted, the object's current owner is used.

    Only actions performed by someone other than the recipient trigger an
    e-mail. A former owner who can no longer open the review detail page
    (ownership transferred before delivery) is skipped. Returns True when
    an e-mail was sent.
    """
    obj = action.content_object
    if recipient is None:
        recipient = getattr(obj, "owner", None) if obj is not None else None
    if (
        obj is None
        or recipient is None
        or recipient.pk == action.user_id
        or not recipient.email
    ):
        return False
    try:
        # The action may carry a content_object cached before an ownership
        # transfer (e.g. the synchronous broker fallback); use committed state.
        obj.refresh_from_db(fields=["owner"])
    except obj.__class__.DoesNotExist:
        return False
    if not _can_open_review_link(recipient, obj):
        logger.info(
            "Skipping review notification for %s %s (action=%s): recipient %s "
            "no longer owns the object.",
            action.content_type.model,
            action.object_id,
            action.action,
            recipient.pk,
        )
        return False

    context = {
        "action": action,
        "actor": action.user,
        "recipient": recipient,
        "object": obj,
        "object_name": getattr(obj, "name", None) or str(obj),
        "object_verbose_name": capfirst(obj._meta.verbose_name),
        "summary": ACTION_SUMMARIES.get(action.action, "was updated during review"),
        "site": _notification_site(),
        "protocol": _notification_protocol(),
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
        [recipient.email],
    )
    logger.info(
        "Sent review notification for %s %s (action=%s) to %s",
        action.content_type.model,
        action.object_id,
        action.action,
        recipient.email,
    )
    return True
