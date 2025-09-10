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

    Mirrors logic from `UserCreatedObjectPermission._is_moderator`:
    - staff users can always moderate
    - otherwise requires app_label.can_moderate_<modelname>
    """
    try:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False):
            return True
        model_name = getattr(getattr(obj, "_meta", None), "model_name", None)
        app_label = getattr(getattr(obj, "_meta", None), "app_label", None)
        if not model_name or not app_label:
            return False
        perm_codename = f"can_moderate_{model_name}"
        return user.has_perm(f"{app_label}.{perm_codename}")
    except Exception:
        return False
