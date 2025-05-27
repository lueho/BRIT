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
