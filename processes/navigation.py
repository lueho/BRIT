"""Navigation helpers for the Processes discovery UI.

Builds the scoped discovery URLs shared by the process lists, the category
catalogue and the detail context navigation. Return-context parameters
(``back``/``next``) are only used to recover filter state: their values are
validated against the host allow-list, restricted to known local discovery
routes and never echoed back into generated links.
"""

from urllib.parse import parse_qsl, unquote, urlsplit

from django.http import QueryDict
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from utils.object_management.permissions import user_is_moderator_for_model

from .models import Process

PROCESS_SCOPES = ("published", "private", "review")

PRESERVED_FILTER_PARAMS = (
    "name",
    "categories",
    "mechanism",
    "input_material",
    "output_material",
    "publication_status",
    "ordering",
    "sort",
)

_SCOPE_LIST_ROUTES = {
    "published": "processes:process-list",
    "private": "processes:process-list-owned",
    "review": "processes:process-list-review",
}

_RETURN_CONTEXT_ROUTES = frozenset(
    {
        "processes:process-list",
        "processes:processtype-list",
        "processes:process-list-owned",
        "processes:process-list-review",
        "processes:processcategory-list",
        "processes:processcategory-list-owned",
        "processes:processcategory-list-review",
        "processes:processcategory-detail",
    }
)

_ROUTE_SCOPES = {
    "processes:process-list-owned": "private",
    "processes:process-list-review": "review",
    "processes:processcategory-list-owned": "private",
    "processes:processcategory-list-review": "review",
}

_RETURN_PATH_PARAMS = frozenset({"back", "next", "return_to"})


def _filtered_query(params):
    """Return a QueryDict holding only the preserved process filter values."""
    filtered = QueryDict(mutable=True)
    for key in PRESERVED_FILTER_PARAMS:
        values = params.getlist(key)
        if values:
            filtered.setlist(key, values)
    return filtered


def _validated_return_context(request):
    """Return ``(query_params, route)`` from a safe ``back``/``next`` parameter.

    The candidate value must pass the host allow-list check, resolve to a
    known local discovery route and must not itself carry nested return
    parameters. Returns ``(None, None)`` otherwise.
    """
    if request is None:
        return None, None
    for key in ("back", "next"):
        raw = request.GET.get(key)
        if not raw:
            continue
        try:
            is_safe = url_has_allowed_host_and_scheme(
                raw,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            )
            parts = urlsplit(raw)
        except ValueError:
            continue
        if not is_safe:
            continue
        if "modal" in unquote(parts.path).split("/"):
            continue
        try:
            match = resolve(parts.path)
        except Resolver404:
            continue
        app_name = match.app_name or (match.namespaces[0] if match.namespaces else "")
        route = f"{app_name}:{match.url_name}" if app_name else match.url_name
        if route not in _RETURN_CONTEXT_ROUTES:
            continue
        params = QueryDict(parts.query)
        if any(name in params for name in _RETURN_PATH_PARAMS):
            continue
        return params, route
    return None, None


def validated_return_url(request):
    """Return a safe local ``back``/``next`` value for 'Back to results'.

    The value must pass the host allow-list check, must not point into a
    modal and must not carry nested return parameters. Returns ``None``
    otherwise.
    """
    if request is None:
        return None
    for key in ("back", "next"):
        raw = request.GET.get(key)
        if not raw:
            continue
        try:
            is_safe = url_has_allowed_host_and_scheme(
                raw,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            )
            parts = urlsplit(raw)
        except ValueError:
            continue
        if not is_safe:
            continue
        if "modal" in unquote(parts.path).split("/"):
            continue
        queries = [parts.query, urlsplit(unquote(raw)).query]
        if any(
            key in _RETURN_PATH_PARAMS
            for query in queries
            for key, _ in parse_qsl(query, keep_blank_values=True)
        ):
            continue
        return raw
    return None


def _normalized_scope(scope, user):
    """Drop scopes the user cannot access: anonymous users get only the
    published context and only process moderators keep ``review``."""
    if scope == "review" and not user_is_moderator_for_model(user, Process):
        return "published"
    if scope == "private" and not (user and user.is_authenticated):
        return "published"
    return scope


def _request_route(request):
    match = getattr(request, "resolver_match", None)
    if match is None:
        return None
    return f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name


def discovery_context(request):
    """Resolve the active process-discovery scope and filters for ``request``.

    Returns a dict with ``scope`` (always a valid process scope, default
    ``published``), ``filters`` (QueryDict of preserved filter parameters,
    without scope) and ``explicit`` (True when the request carried an explicit
    scope, explicit filters, or a recognized local return context).
    """
    if request is None:
        return {
            "scope": "published",
            "filters": QueryDict(mutable=True),
            "explicit": False,
        }

    filters = _filtered_query(request.GET)
    scope = request.GET.get("scope")
    explicit = scope in PROCESS_SCOPES or bool(filters)
    if scope not in PROCESS_SCOPES:
        scope = None

    if scope is None or not filters:
        return_params, route = _validated_return_context(request)
        if return_params is not None:
            explicit = True
            if not filters:
                filters = _filtered_query(return_params)
            if scope is None:
                scope = return_params.get("scope")
                if scope not in PROCESS_SCOPES:
                    scope = _ROUTE_SCOPES.get(route)

    if scope is None:
        scope = _ROUTE_SCOPES.get(_request_route(request))

    scope = _normalized_scope(scope, getattr(request, "user", None))
    if scope is None:
        scope = "published"

    return {"scope": scope, "filters": filters, "explicit": explicit}


def _scoped_params(scope, filters):
    params = filters.copy() if filters else QueryDict(mutable=True)
    params["scope"] = scope
    return params


def process_scope_url(scope, filters=None):
    """URL of the process list for ``scope`` carrying the preserved filters."""
    params = _scoped_params(scope, filters)
    return f"{reverse(_SCOPE_LIST_ROUTES[scope])}?{params.urlencode()}"


def scope_switch_url(
    request, scope, base_url=None, keep_category_q=False, filters=None
):
    """Scope-switch URL keeping filters but dropping ``publication_status``.

    ``base_url`` defaults to the process list for ``scope``; the category
    pages pass their own path so switching scope stays on the same page.
    ``filters`` defaults to the request's own filter parameters; pass the
    resolved discovery filters to keep filters recovered from ``back``/``next``.
    """
    if filters is not None:
        filters = filters.copy()
    elif request:
        filters = _filtered_query(request.GET)
    else:
        filters = QueryDict(mutable=True)
    filters.pop("publication_status", None)
    filters["scope"] = scope
    if keep_category_q:
        category_q = (request.GET.get("category_q") or "").strip()
        if category_q:
            filters["category_q"] = category_q
    if base_url is None:
        base_url = reverse(_SCOPE_LIST_ROUTES[scope])
    return f"{base_url}?{filters.urlencode()}"


def categories_url(scope, filters=None):
    """URL of the category catalogue carrying the process scope and filters."""
    params = _scoped_params(scope, filters)
    return f"{reverse('processes:processcategory-list')}?{params.urlencode()}"


def _category_params(category, scope, filters):
    params = filters.copy() if filters else QueryDict(mutable=True)
    params.setlist("categories", [str(category.pk)])
    params.pop("page", None)
    params["scope"] = scope
    return params


def category_detail_url(category, scope, filters=None):
    """URL of a category detail page carrying the process scope and filters.

    The carried category selection is replaced by ``category`` so the
    gallery is not restricted to a previously selected category.
    """
    params = _category_params(category, scope, filters)
    base = reverse("processes:processcategory-detail", kwargs={"pk": category.pk})
    return f"{base}?{params.urlencode()}"


def category_process_list_url(category, scope, filters=None):
    """Scoped process list URL filtered to a single category.

    Any previously selected categories are replaced by ``category`` and
    pagination is reset.
    """
    params = _category_params(category, scope, filters)
    return f"{reverse(_SCOPE_LIST_ROUTES[scope])}?{params.urlencode()}"
