"""E-mail notifications for the review workflow."""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import capfirst

from .models import ReviewAction, ReviewNotificationMute
from .policy import decide

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
    """Mirror ``ReviewItemDetailView`` access via ``view_review_activity``.

    Evaluated at delivery time, so revoked grants or ownership transfers are
    honored even when the action predates the change.
    """
    return decide(user, "view_review_activity", obj).allowed


_CURRENT_OWNER = object()


def _user_wants_review_emails(user):
    """Return False when the user disabled review e-mails in their profile."""
    profile = getattr(user, "profile", None)
    return profile is None or profile.review_notifications


def _review_participants(action, owner):
    """Return notification candidates for ``action``.

    Candidates are the object's owner (the user captured by the post-save
    signal when the action was created) plus every distinct user who
    commented on the object before ``action``. Comments made after the
    action do not qualify, even when delivery lags behind them. Duplicates
    are removed; the actor is filtered out here and again per-recipient
    when sending.
    """
    recipients = []
    seen = set()
    if owner is not None:
        recipients.append(owner)
        seen.add(owner.pk)
    commenter_ids = (
        ReviewAction.objects.filter(
            content_type_id=action.content_type_id,
            object_id=action.object_id,
            action=ReviewAction.ACTION_COMMENT,
        )
        .filter(
            Q(created_at__lt=action.created_at)
            | Q(created_at=action.created_at, pk__lt=action.pk)
        )
        .exclude(user_id=action.user_id)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for user in User.objects.filter(pk__in=commenter_ids).order_by("pk"):
        if user.pk not in seen:
            seen.add(user.pk)
            recipients.append(user)
    return recipients


def review_notification_recipients(action, owner=_CURRENT_OWNER):
    """Return the users to notify about ``action``.

    ``owner`` is the user who owned the object when the action was
    created; the post-save signal captures it so an ownership transfer
    between enqueue and delivery does not redirect the notification. Pass
    ``None`` when the captured owner no longer exists so that only past
    commenters are returned. When omitted, the object's current owner is
    used. Past commenters are resolved from ``ReviewAction`` rows.
    """
    obj = action.content_object
    if obj is None:
        return []
    if owner is _CURRENT_OWNER:
        owner = getattr(obj, "owner", None)
    return _review_participants(action, owner)


def notify_review_participants(action, owner=_CURRENT_OWNER):
    """E-mail the owner and past commenters about a review action in-process.

    See ``review_notification_recipients`` for the meaning of ``owner``.
    Returns the number of e-mails sent.
    """
    sent = 0
    for recipient in review_notification_recipients(action, owner):
        if send_review_action_notification(action, recipient):
            sent += 1
    return sent


def send_review_action_notification(action, recipient):
    """Send a review notification e-mail for ``action`` to ``recipient``.

    Only actions performed by someone other than the recipient trigger an
    e-mail. Recipients who disabled review e-mails or muted this object,
    and recipients who can no longer open the review detail page (e.g. a
    former owner after an ownership transfer), are skipped. Returns True
    when an e-mail was sent.
    """
    obj = action.content_object
    if (
        obj is None
        or recipient is None
        or recipient.pk == action.user_id
        or not recipient.email
        or not _user_wants_review_emails(recipient)
    ):
        return False
    try:
        # The action may carry a content_object cached before an ownership
        # transfer (e.g. the synchronous broker fallback); use committed state.
        obj.refresh_from_db(fields=["owner"])
    except obj.__class__.DoesNotExist:
        return False
    if ReviewNotificationMute.objects.filter(
        user_id=recipient.pk,
        content_type_id=action.content_type_id,
        object_id=action.object_id,
    ).exists():
        return False
    if not _can_open_review_link(recipient, obj):
        logger.info(
            "Skipping review notification for %s %s (action=%s): recipient %s "
            "cannot open the review page.",
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
        "is_owner": recipient.pk == obj.owner_id,
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
        "mute_url": reverse(
            "object_management:review_notification_mute",
            kwargs={
                "content_type_id": action.content_type_id,
                "object_id": action.object_id,
            },
        ),
        "profile_url": reverse("user_profile"),
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
