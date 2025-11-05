import logging
from urllib.parse import quote

from django import template
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

register = template.Library()


def _safe_policy_fallback(user, obj, review_mode=False, error_message=None):
    """
    Build a minimal, safe policy dictionary using only simple attribute access.
    This is used when the full get_object_policy import/call fails, so that
    templates still receive useful information for debugging.
    """
    try:
        is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    except Exception:
        is_authenticated = False
    try:
        is_staff = bool(getattr(user, "is_staff", False))
    except Exception:
        is_staff = False
    try:
        is_owner = bool(
            is_authenticated
            and getattr(obj, "owner_id", None) == getattr(user, "id", None)
        )
    except Exception:
        is_owner = False

    # Publication status flags (prefer convenience attributes if present)
    def _flag(name, fallback_value):
        try:
            return bool(getattr(obj, name, False))
        except Exception:
            return bool(fallback_value)

    is_private = _flag("is_private", False)
    is_in_review = _flag("is_in_review", False)
    is_published = _flag("is_published", False)
    is_declined = _flag("is_declined", False)
    is_archived = _flag("is_archived", False)

    try:
        status = getattr(obj, "publication_status", None)
        if status == "private":
            is_private = True if not is_private else is_private
        elif status == "review":
            is_in_review = True if not is_in_review else is_in_review
        elif status == "published":
            is_published = True if not is_published else is_published
        elif status == "declined":
            is_declined = True if not is_declined else is_declined
        elif status == "archived":
            is_archived = True if not is_archived else is_archived
    except Exception:
        pass

    export_list_type = (
        "published"
        if (is_published or is_archived)
        else ("private" if (is_owner or is_staff) else None)
    )

    policy = {
        "is_authenticated": is_authenticated,
        "is_owner": is_owner,
        "is_staff": is_staff,
        "is_moderator": False,
        "is_private": is_private,
        "is_in_review": is_in_review,
        "is_published": is_published,
        "is_declined": is_declined,
        "is_archived": is_archived,
        # Conservative defaults for actions
        "can_edit": False,
        "can_manage_samples": False,
        "can_add_property": False,
        "can_duplicate": False,
        "can_new_version": False,
        "can_archive": False,
        "can_delete": False,
        "can_submit_review": False,
        "can_withdraw_review": False,
        "can_approve": False,
        "can_reject": False,
        "can_export": (is_published or is_archived)
        or (is_authenticated and (is_owner or is_staff)),
        "export_list_type": export_list_type,
        "can_view_review_feedback": bool(
            is_owner and is_declined and not bool(review_mode)
        ),
        # Fallback marker
        "fallback": True,
    }
    if error_message:
        policy["policy_error"] = error_message
    return policy


@register.filter
def get_content_type_id(obj):
    """
    Returns the content type ID for a given object.
    Usage: {{ object|get_content_type_id }}
    """
    return ContentType.objects.get_for_model(obj).id


@register.filter
def can_moderate(user, obj):
    """Return True if the user can moderate the given object.

    Usage in templates:
        {% if user|can_moderate:object %}
            ...
        {% endif %}

    Delegates to `UserCreatedObjectPermission.is_moderator` to keep parity
    with backend checks. Falls back to staff on unexpected errors.
    """
    logger = logging.getLogger(__name__)
    try:
        # Local import to avoid app loading issues
        from utils.object_management.permissions import UserCreatedObjectPermission

        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False):
            return True
        return UserCreatedObjectPermission().is_moderator(user, obj)
    except Exception:
        logger.exception("Error in can_moderate templatetag", exc_info=True)
        return bool(getattr(user, "is_staff", False))


@register.simple_tag(takes_context=True)
def object_policy(context, obj, review_mode=False):
    """
    Return a unified policy dict for the given object.

    Usage in templates:
        {% object_policy object as policy %}
        {% if policy.can_edit %} ... {% endif %}

    Optional parameter `review_mode` allows templates rendered in review contexts
    to hide owner-only feedback hints.
    """
    logger = logging.getLogger(__name__)
    try:
        request = context.get("request")
        user = getattr(request, "user", None) or context.get("user")
        # Local import to avoid circular imports at app load
        from utils.object_management.permissions import (
            get_object_policy as _get_object_policy,
        )

        result = _get_object_policy(user, obj, request=request, review_mode=review_mode)
        return result
    except Exception as e:
        logger.exception("object_policy tag failed", exc_info=True)
        # Show error to staff users regardless of DEBUG; otherwise show in DEBUG only
        try:
            request = context.get("request")
            user = getattr(request, "user", None)
            # Reveal to staff
            if (
                user is not None
                and getattr(user, "is_authenticated", False)
                and getattr(user, "is_staff", False)
            ):
                return _safe_policy_fallback(
                    user, obj, review_mode, f"{type(e).__name__}: {e}"
                )
            # Reveal to owner of the object as well (helps debugging private pages)
            try:
                if user is not None and getattr(user, "is_authenticated", False):
                    owner_id = getattr(obj, "owner_id", None)
                    if owner_id == getattr(user, "id", None):
                        return _safe_policy_fallback(
                            user, obj, review_mode, f"{type(e).__name__}: {e}"
                        )
            except Exception:
                pass
        except Exception:
            pass
        try:
            if getattr(settings, "DEBUG", False):
                # In debug, reveal error and fallback too
                return _safe_policy_fallback(
                    user, obj, review_mode, f"{type(e).__name__}: {e}"
                )
        except Exception:
            pass
        # Last resort: minimal fallback without error message
        return _safe_policy_fallback(user, obj, review_mode)


@register.simple_tag(takes_context=True)
def detail_or_review_url(context, obj, use_back=False):
    """
    Return the URL that should be used to view the object in list/filter UIs.

    If the object's publication status is 'review' (or obj.is_in_review is True)
    and the current user is allowed to access the review UI for this object
    (staff or per‑model moderator and NOT the owner), return the review view URL
    with a ?next=<current_path> parameter so that actions can navigate back.

    Otherwise, return the object's regular absolute URL.
    """
    logger = logging.getLogger(__name__)
    request = context.get("request")
    user = getattr(request, "user", None)

    # Resolve absolute URL safely whether implemented as method or property
    try:
        getter = getattr(obj, "get_absolute_url", None)
        if callable(getter):
            absolute_url = getter()
        else:
            absolute_url = getter or "#"
    except Exception:
        absolute_url = "#"

    # Guard: if no publication status semantics, use absolute URL
    try:
        # Prefer attribute access guarded by hasattr to satisfy lint B009
        if hasattr(obj, "is_in_review") and bool(obj.is_in_review):
            in_review = True
        else:
            in_review = getattr(obj, "publication_status", None) == "review"
    except Exception:
        in_review = False

    # Owners of declined items should be redirected to the review feedback view
    try:
        is_declined = getattr(obj, "is_declined", None)
        if is_declined is None:
            is_declined = getattr(obj, "publication_status", None) == "declined"
    except Exception:
        is_declined = False

    if is_declined and user and getattr(user, "is_authenticated", False):
        owner_id = getattr(obj, "owner_id", None)
        if owner_id == getattr(user, "id", None):
            try:
                ct = ContentType.objects.get_for_model(obj.__class__)
                review_url = reverse(
                    "object_management:review_item_detail",
                    kwargs={"content_type_id": ct.id, "object_id": obj.pk},
                )
                next_param = ""
                try:
                    if request is not None:
                        next_param = (
                            f"?next={quote(request.get_full_path or '', safe='')}"
                        )
                except Exception:  # pragma: no cover - defensive
                    next_param = ""
                return f"{review_url}{next_param}"
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(
                    "detail_or_review_url: failed building owner review URL: %s", e
                )

    # Owners of items currently in review should be redirected to the review view so they can comment
    try:
        if in_review and user and getattr(user, "is_authenticated", False):
            owner_id = getattr(obj, "owner_id", None)
            if owner_id == getattr(user, "id", None):
                try:
                    ct = ContentType.objects.get_for_model(obj.__class__)
                    review_url = reverse(
                        "object_management:review_item_detail",
                        kwargs={"content_type_id": ct.id, "object_id": obj.pk},
                    )
                    next_param = ""
                    try:
                        if request is not None:
                            next_param = (
                                f"?next={quote(request.get_full_path or '', safe='')}"
                            )
                    except Exception:  # pragma: no cover - defensive
                        next_param = ""
                    return f"{review_url}{next_param}"
                except Exception as e:  # pragma: no cover - defensive
                    logger.warning(
                        "detail_or_review_url: failed building owner-in-review URL: %s",
                        e,
                    )
    except Exception:
        pass

    if not in_review:
        # Optionally include ?back=<current_path> for detail pages coming from lists
        if use_back and request is not None:
            try:
                return (
                    f"{absolute_url}?back={quote(request.get_full_path or '', safe='')}"
                )
            except Exception:  # pragma: no cover - defensive
                return absolute_url
        return absolute_url

    # Only allow redirect to review view for moderators/staff who are not the owner
    try:
        owner_id = getattr(obj, "owner_id", None)
        is_owner = bool(
            user
            and getattr(user, "is_authenticated", False)
            and owner_id == getattr(user, "id", None)
        )
        is_staff = bool(getattr(user, "is_staff", False))

        # Local import to avoid circulars
        from utils.object_management.permissions import UserCreatedObjectPermission

        is_moderator = False
        if user and getattr(user, "is_authenticated", False):
            try:
                is_moderator = is_staff or UserCreatedObjectPermission().is_moderator(
                    user, obj
                )
            except Exception:
                is_moderator = is_staff

        if (
            user
            and getattr(user, "is_authenticated", False)
            and (is_moderator and not is_owner)
        ):
            try:
                ct = ContentType.objects.get_for_model(obj.__class__)
                review_url = reverse(
                    "object_management:review_item_detail",
                    kwargs={"content_type_id": ct.id, "object_id": obj.pk},
                )
                next_param = ""
                try:
                    if request is not None:
                        next_param = (
                            f"?next={quote(request.get_full_path or '', safe='')}"
                        )
                except Exception:  # pragma: no cover - defensive
                    next_param = ""
                return f"{review_url}{next_param}"
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(
                    "detail_or_review_url: failed building review URL: %s", e
                )
                return absolute_url
        else:
            # Not eligible for review view; optionally add back param
            if use_back and request is not None:
                try:
                    return f"{absolute_url}?back={quote(request.get_full_path or '', safe='')}"
                except Exception:  # pragma: no cover - defensive
                    return absolute_url
            return absolute_url
    except Exception:  # pragma: no cover - defensive
        return absolute_url


@register.simple_tag
def is_moderator_for_any_model(user):
    """Check if user has moderation permissions for any UserCreatedObject model.

    Returns True if the user is staff or has can_moderate_* permission for any model.
    This is useful for showing/hiding moderator-specific UI elements.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    # Staff users are always moderators
    if getattr(user, "is_staff", False):
        return True

    # Check if user has any can_moderate_* permission
    try:
        from utils.object_management.models import UserCreatedObject

        for model in apps.get_models():
            if (
                issubclass(model, UserCreatedObject)
                and not model._meta.abstract
            ):
                perm_codename = f"can_moderate_{model._meta.model_name}"
                full_perm = f"{model._meta.app_label}.{perm_codename}"
                if user.has_perm(full_perm):
                    return True
    except Exception:
        # If something goes wrong, fail closed
        return False

    return False


@register.simple_tag
def pending_review_count_for_user(user):
    """Count items pending review that the user can moderate.

    Returns the total count of items in review status across all models
    where the user has moderation permissions (excluding their own items).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return 0

    try:
        from utils.object_management.models import UserCreatedObject
        from utils.object_management.permissions import user_is_moderator_for_model

        total_count = 0

        for model in apps.get_models():
            if (
                issubclass(model, UserCreatedObject)
                and not model._meta.abstract
                and hasattr(model, "objects")
            ):
                if user_is_moderator_for_model(user, model):
                    try:
                        # Count items in review, excluding user's own items
                        count = (
                            model.objects.in_review()
                            .exclude(owner=user)
                            .count()
                        )
                        total_count += count
                    except Exception:
                        # Skip models that don't support the query
                        continue

        return total_count
    except Exception:
        # If something goes wrong, return 0
        return 0
