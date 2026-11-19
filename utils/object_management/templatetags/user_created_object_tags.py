from django import template
from django.http import QueryDict

register = template.Library()


@register.filter
def is_user_created(model_class):
    return getattr(model_class, "user_created", False)


_SCOPE_DROP_PARAMS = ("scope", "id", "page", "publication_status")

_SCOPE_URL_CONTEXT_KEYS = {
    "published": "public_representation_url",
    "private": "private_representation_url",
    "review": "review_representation_url",
}


@register.simple_tag(takes_context=True)
def scope_toggle_urls(context):
    """Per-scope list URLs for the shared scope toggle.

    Carries the request's filter parameters (including repeated values) into
    each scope's representation URL and drops navigation and scope-state
    parameters.
    """
    request = context.get("request")
    params = request.GET.copy() if request else QueryDict(mutable=True)
    for key in _SCOPE_DROP_PARAMS:
        params.pop(key, None)
    urls = {}
    for scope, context_key in _SCOPE_URL_CONTEXT_KEYS.items():
        base = context.get(context_key)
        if base:
            scoped = params.copy()
            scoped["scope"] = scope
            urls[scope] = f"{base}?{scoped.urlencode()}"
    return urls
