import logging
import re
from importlib import import_module
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from django import template
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from django.utils.html import escape, mark_safe
from django.utils.http import url_has_allowed_host_and_scheme

register = template.Library()

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_LEGACY_SECTION_SEPARATOR_RE = re.compile(r"(?:\s*;\s*){2,}")


# Params that carry a return path back into the app. They are stripped before
# embedding the current path into a new back/next/return_to param so the value
# can never nest — otherwise each list->detail->list round trip doubles the URL
# and crawlers discover an unbounded URL space.
_RETURN_PATH_PARAMS = frozenset({"back", "next", "return_to"})


def _fully_unquoted(value, max_rounds=5):
    for _ in range(max_rounds):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


@register.simple_tag(takes_context=True)
def safe_back_url(context):
    request = context.get("request")
    if request is None:
        return ""

    back = request.GET.get("back")
    if not back:
        return ""

    try:
        is_safe = url_has_allowed_host_and_scheme(
            back,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        nested_params = parse_qsl(urlsplit(back).query, keep_blank_values=True)
    except ValueError:
        return ""

    if not is_safe:
        return ""

    # Modal endpoints render bare fragments; they are never a page to return to.
    if "modal" in _fully_unquoted(urlsplit(back).path).split("/"):
        return ""

    # A value that itself carries return-path params is a leftover of the
    # unbounded nesting trap; echoing it keeps feeding crawlers the trap.
    if any(key in _RETURN_PATH_PARAMS for key, _ in nested_params):
        return ""

    return back


@register.simple_tag(takes_context=True)
def safe_next_url(context):
    """Return the request's ``next`` param if it is a same-host URL, else ``""``."""
    request = context.get("request")
    if request is None:
        return ""

    next_url = request.GET.get("next")
    if not next_url:
        return ""

    try:
        is_safe = url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    except ValueError:
        return ""
    return next_url if is_safe else ""


@register.filter
def markdown_to_html(value):
    """Render a deliberately limited markdown subset.

    Supported features:
    - Bold text via ``**bold**``
    - Unordered lists via ``- item`` or ``* item``
    - Ordered lists via ``1. item``

    Any other markdown syntax (e.g. headings) is rendered as plain text.
    """
    text = "" if value is None else str(value)
    return mark_safe(_render_limited_markdown(text))


@register.filter
def collection_description_to_html(value):
    text = _normalize_collection_description(value)
    return mark_safe(_render_limited_markdown(text))


def _normalize_collection_description(value):
    try:
        module = import_module("sources.waste_collection.description_formatting")
    except (ImportError, ModuleNotFoundError):
        text = "" if value is None else str(value)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if _LEGACY_SECTION_SEPARATOR_RE.search(text) is None:
            return text
        parts = [part.strip() for part in _LEGACY_SECTION_SEPARATOR_RE.split(text)]
        return "\n".join(part for part in parts if part)
    return module.normalize_collection_description(value)


def _render_limited_markdown(text: str) -> str:
    """Convert a small markdown subset to safe HTML."""
    html_parts: list[str] = []
    list_items: list[str] = []
    current_list_tag: str | None = None

    def flush_list() -> None:
        nonlocal list_items, current_list_tag
        if not list_items or not current_list_tag:
            return
        html_parts.append(f"<{current_list_tag}>")
        for item in list_items:
            html_parts.append(f"<li>{item}</li>")
        html_parts.append(f"</{current_list_tag}>")
        list_items = []
        current_list_tag = None

    for raw_line in text.splitlines():
        unordered = re.match(r"^\s*[-*]\s+(.*)$", raw_line)
        ordered = re.match(r"^\s*\d+\.\s+(.*)$", raw_line)

        if unordered:
            if current_list_tag not in {None, "ul"}:
                flush_list()
            current_list_tag = "ul"
            list_items.append(_render_inline_limited(unordered.group(1)))
            continue

        if ordered:
            if current_list_tag not in {None, "ol"}:
                flush_list()
            current_list_tag = "ol"
            list_items.append(_render_inline_limited(ordered.group(1)))
            continue

        flush_list()
        stripped = raw_line.strip()
        if stripped:
            html_parts.append(f"<p>{_render_inline_limited(stripped)}</p>")

    flush_list()
    return "".join(html_parts)


def _render_inline_limited(text: str) -> str:
    """Render safe inline markdown (bold only)."""
    escaped = escape(text)
    return _BOLD_PATTERN.sub(r"<strong>\1</strong>", escaped)


def _safe_policy_fallback(user, obj, review_mode=False):
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

    has_review_feedback = bool(is_owner and getattr(obj, "has_review_feedback", False))
    review_feedback_label = "Review feedback" if is_declined else "Review activity"

    policy = {
        "is_authenticated": is_authenticated,
        "is_owner": is_owner,
        "is_staff": is_staff,
        "is_admin": False,
        "is_moderator": False,
        "is_editor": False,
        "is_private": is_private,
        "is_in_review": is_in_review,
        "is_published": is_published,
        "is_declined": is_declined,
        "is_archived": is_archived,
        "has_change_permission": False,
        "has_update_url": False,
        "has_delete_url": False,
        "can_read": False,
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
        "can_transfer_ownership": False,
        "can_manage_editors": False,
        "can_view_review_activity": False,
        "can_comment_on_review": False,
        "can_export": False,
        "export_list_type": None,
        "has_review_feedback": has_review_feedback,
        "review_feedback_label": review_feedback_label,
        "can_view_review_feedback": False,
        "reason_codes": {},
        # Fallback marker
        "fallback": True,
    }
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

    Delegates to the shared policy helpers; the raw ``is_staff`` flag alone
    never implies moderation rights.
    """
    logger = logging.getLogger(__name__)
    try:
        # Local import to avoid app loading issues
        from utils.object_management.permissions import user_is_moderator_for_model

        if not user or not getattr(user, "is_authenticated", False):
            return False
        model = obj if isinstance(obj, type) else obj.__class__
        return user_is_moderator_for_model(user, model)
    except Exception:
        logger.exception("Error in can_moderate templatetag", exc_info=True)
        return False


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
    request = context.get("request")
    user = getattr(request, "user", None) or context.get("user")
    try:
        # Local import to avoid circular imports at app load
        from utils.object_management.permissions import (
            get_object_policy as _get_object_policy,
        )

        return _get_object_policy(user, obj, request=request, review_mode=review_mode)
    except Exception:
        logger.exception("object_policy tag failed", exc_info=True)
        return _safe_policy_fallback(user, obj, review_mode)


@register.filter
def path_without_return_params(request):
    """Current full path minus any return-path params."""
    parts = urlsplit(request.get_full_path())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in _RETURN_PATH_PARAMS
        ]
    )
    return urlunsplit(("", "", parts.path, query, parts.fragment))


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
                        next_param = f"?next={quote(path_without_return_params(request), safe='')}"
                except Exception:  # pragma: no cover - defensive
                    next_param = ""
                return f"{review_url}{next_param}"
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(
                    "detail_or_review_url: failed building owner review URL: %s", e
                )

    try:
        if (
            (in_review or is_declined)
            and user
            and getattr(user, "is_authenticated", False)
        ):
            from utils.object_management.policy import decide as _decide

            if _decide(user, "view_review_activity", obj).allowed:
                try:
                    ct = ContentType.objects.get_for_model(obj.__class__)
                    review_url = reverse(
                        "object_management:review_item_detail",
                        kwargs={"content_type_id": ct.id, "object_id": obj.pk},
                    )
                    next_param = ""
                    try:
                        if request is not None:
                            next_param = f"?next={quote(path_without_return_params(request), safe='')}"
                    except Exception:  # pragma: no cover - defensive
                        next_param = ""
                    return f"{review_url}{next_param}"
                except Exception as e:  # pragma: no cover - defensive
                    logger.warning(
                        "detail_or_review_url: failed building review URL: %s", e
                    )
    except Exception:
        pass

    if use_back and request is not None:
        try:
            return f"{absolute_url}?back={quote(path_without_return_params(request), safe='')}"
        except Exception:  # pragma: no cover - defensive
            return absolute_url
    return absolute_url


@register.simple_tag
def is_moderator_for_any_model(user):
    """Check if user can moderate any registered reviewable model.

    True for administrators and holders of any ``can_moderate_*`` permission;
    the raw ``is_staff`` flag alone grants nothing. Results are cached for
    20 minutes to reduce database load.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    # Use cache to avoid repeated permission checks
    cache_key = f"is_moderator_any_model_{user.id}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        from utils.object_management.permissions import user_is_moderator_for_model
        from utils.object_management.registry import (
            KIND_REVIEWABLE,
            registered_models,
        )

        for model in registered_models(kind=KIND_REVIEWABLE):
            if model is not None and user_is_moderator_for_model(user, model):
                cache.set(cache_key, True, 1200)
                return True
    except Exception:
        # If something goes wrong, fail closed
        return False

    # Cache the negative result for 20 minutes. Permission and review-status
    # signals clear this cache when needed.
    cache.set(cache_key, False, 1200)
    return False


@register.simple_tag(takes_context=True)
def model_creation_policy(context, model, parent=None):
    """Return the policy ``Decision`` for creating ``model``.

    Usage:
        {% model_creation_policy field.field.queryset.model as create_policy %}
        {% if create_policy.allowed %} ... {% endif %}
    """
    from utils.object_management.policy import Decision, decide

    request = context.get("request")
    user = getattr(request, "user", None)
    try:
        return decide(user, "create", model, parent=parent)
    except Exception:
        logging.getLogger(__name__).exception(
            "model_creation_policy tag failed", exc_info=True
        )
        return Decision(False, "error")


@register.simple_tag
def has_pending_review_items_for_user(user):
    """Return whether the user can moderate any pending review items.

    This intentionally avoids counting all review items because the shared
    navigation only needs a simple indicator.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    # Use cache to avoid repeated database queries
    cache_key = f"has_pending_review_items_{user.id}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        from utils.object_management.views import ReviewDashboardView

        request = RequestFactory().get("/")
        request.user = user

        view = ReviewDashboardView()
        view.setup(request)
        view.request = request
        has_items = view.has_review_items()

        # Cache the result for 20 minutes. This badge appears in the shared
        # navigation, so cold checks otherwise affect unrelated pages.
        cache.set(cache_key, has_items, 1200)
        return has_items
    except Exception:
        # If something goes wrong, return no signal.
        return False


def clear_moderation_cache_for_user(user_id):
    """Clear moderation-related cache for a specific user."""
    cache_keys = [
        f"has_pending_review_items_{user_id}",
        f"is_moderator_any_model_{user_id}",
    ]
    for key in cache_keys:
        cache.delete(key)


def clear_all_moderation_cache():
    """Clear all moderation-related cache entries.

    This should be called when publication statuses change in bulk
    or when permissions are modified.
    """
    # This is a more aggressive cache clearing approach
    # In production, you might want to use a more targeted approach
    try:
        # Clear all cache keys that match our moderation patterns
        # Note: This requires a cache backend that supports pattern deletion
        # For Redis or similar, you could use:
        # cache.delete_many([key for key in cache.keys('*has_pending_review_items_*')])
        # cache.delete_many([key for key in cache.keys('*is_moderator_any_model_*')])

        # For simplicity, we'll just let the cache expire naturally
        # In a real implementation, you'd want proper cache invalidation
        pass
    except Exception:
        # If cache clearing fails, it's not critical - the cache will expire
        pass
