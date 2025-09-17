import logging
from django import template
from django.contrib.contenttypes.models import ContentType

register = template.Library()


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
    try:
        request = context.get("request")
        user = getattr(request, "user", None) or context.get("user")
        # Local import to avoid circular imports at app load
        from utils.object_management.permissions import (
            get_object_policy as _get_object_policy,
        )

        return _get_object_policy(user, obj, request=request, review_mode=review_mode)
    except Exception:
        return {}
