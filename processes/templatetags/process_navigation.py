"""Template tags for the Processes discovery navigation."""

from django import template

from utils.object_management.permissions import user_is_moderator_for_model

from ..models import Process
from ..navigation import (
    PROCESS_SCOPES,
    categories_url,
    category_detail_url,
    category_process_list_url,
    discovery_context,
    process_scope_url,
    scope_switch_url,
    validated_return_url,
)

register = template.Library()


def _authoritative_scope(context):
    """Return the list_type scope when the current page lists processes.

    On process lists the view's ``list_type`` is the authoritative scope; on
    category pages the same context variable would describe the category
    management scope and must be ignored.
    """
    object_list = context.get("object_list")
    if getattr(object_list, "model", None) is Process:
        list_type = context.get("list_type")
        if list_type in PROCESS_SCOPES:
            return list_type
    return None


def _nav_context(context, section):
    request = context.get("request")
    nav = discovery_context(request)
    scope = _authoritative_scope(context) or nav["scope"]
    filters = nav["filters"]
    user = getattr(request, "user", None)
    process_scope_urls = {
        item: process_scope_url(item, filters) for item in PROCESS_SCOPES
    }
    if section == "processes" or request is None:
        scope_urls = {
            item: scope_switch_url(request, item, filters=filters)
            for item in PROCESS_SCOPES
        }
    else:
        scope_urls = {
            item: scope_switch_url(
                request,
                item,
                base_url=request.path,
                keep_category_q=True,
                filters=filters,
            )
            for item in PROCESS_SCOPES
        }
    return {
        "nav_section": section,
        "nav_scope": scope,
        "nav_processes_url": process_scope_urls[scope],
        "nav_categories_url": categories_url(scope, filters),
        "nav_scope_urls": scope_urls,
        "nav_show_scopes": section != "processes",
        "nav_show_private": bool(user and user.is_authenticated),
        "nav_show_review": user_is_moderator_for_model(user, Process),
    }


@register.inclusion_tag(
    "processes/includes/process_discovery_nav.html", takes_context=True
)
def process_discovery_nav(context, section, compact=False):
    """Render the Processes | Categories discovery navigation.

    ``section`` is ``"processes"`` or ``"categories"`` and marks the active
    tab. ``compact`` renders only the two section links, for the shared
    detail context navigation.
    """
    nav = _nav_context(context, section)
    nav["nav_compact"] = compact
    return nav


@register.simple_tag(takes_context=True)
def process_category_filter_url(context, category):
    """Scoped process list URL filtered to ``category`` only.

    Other active process filters and the scope are preserved; pagination is
    reset and previous category selections are replaced.
    """
    nav = discovery_context(context.get("request"))
    scope = _authoritative_scope(context) or nav["scope"]
    return category_process_list_url(category, scope, nav["filters"])


@register.simple_tag(takes_context=True)
def process_category_about_url(context, category):
    """Category detail URL carrying the current process scope and filters."""
    nav = discovery_context(context.get("request"))
    scope = _authoritative_scope(context) or nav["scope"]
    return category_detail_url(category, scope, nav["filters"])


@register.simple_tag(takes_context=True)
def process_scope_switch_url(context, scope):
    """Process-list URL for ``scope`` preserving filters incl. repeated
    ``categories`` and dropping ``publication_status``."""
    return scope_switch_url(context.get("request"), scope)


@register.simple_tag(takes_context=True)
def process_filter_params(context):
    """QueryDict of preserved process filter parameters for the request."""
    return discovery_context(context.get("request"))["filters"]


@register.simple_tag(takes_context=True)
def process_categories_url(context):
    """Category catalogue URL for the current scope and filters."""
    nav = discovery_context(context.get("request"))
    scope = _authoritative_scope(context) or nav["scope"]
    return categories_url(scope, nav["filters"])


@register.simple_tag(takes_context=True)
def process_return_url(context):
    """Validated local ``back``/``next`` value for 'Back to results'."""
    return validated_return_url(context.get("request"))
