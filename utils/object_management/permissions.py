import logging

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from rest_framework import exceptions as drf_exceptions
from rest_framework import permissions

from .policy import (
    capabilities,
    decide,
    is_admin,
    is_editor,
    is_moderator,
    is_owner,
    scope_queryset,
    visible_queryset,
)
from .registry import (
    KIND_GENERATED,
    KIND_OWNED,
    generated_profile,
    model_policy,
    record_policy,
    resolve_parent,
    review_target,
)

logger = logging.getLogger(__name__)

_PROPERTY_CHILD_LABEL = {
    ("materials", "sample"): "materials.materialpropertyvalue",
    ("waste_collection", "collection"): "waste_collection.collectionpropertyvalue",
}

OBJECT_ACTION_MAP = {
    "retrieve": "read",
    "update": "edit",
    "partial_update": "edit",
    "destroy": "delete",
    "register_for_review": "submit",
    "submit_for_review": "submit",
    "submit": "submit",
    "withdraw_from_review": "withdraw",
    "withdraw": "withdraw",
    "approve": "approve",
    "reject": "reject",
    "archive": "archive",
    "new_version": "new_version",
    "create_new_version": "new_version",
    "duplicate": "duplicate",
    "comment": "comment_on_review",
    "add_review_comment": "comment_on_review",
}

FORBIDDEN_WRITE_PAYLOAD_FIELDS = frozenset(
    {
        "owner",
        "publication_status",
        "content_revision",
        "submitted_at",
        "approved_at",
        "approved_by",
    }
)


def _forbidden_write_fields(model):
    """Server-controlled fields a write payload may never carry.

    In addition to the shared lifecycle metadata, generated-projection
    profiles declare their marker and source pointer read-only: the marker
    and linkage are assigned by the derivation pipeline, never by a public
    payload.
    """
    forbidden = set(FORBIDDEN_WRITE_PAYLOAD_FIELDS)
    profile = generated_profile(model) if model is not None else None
    if profile is not None:
        forbidden.update(profile)
    return forbidden


class GlobalObjectPermission(permissions.BasePermission):
    """Allow global-object reads for everyone and writes for administrators."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return is_admin(request.user)


class UserCreatedObjectPermission(permissions.BasePermission):
    """DRF adapter delegating to :mod:`utils.object_management.policy`.

    Action-level checks resolve the view's model and delegate to
    ``policy.decide``; object-level checks map DRF actions and named review
    actions onto the same object actions. Adapters may narrow decisions but
    never broaden them.
    """

    def _get_view_model(self, view):
        """Return the model class exposed by ``view`` or ``None``."""
        model = None
        queryset = getattr(view, "queryset", None)
        if queryset is not None:
            model = getattr(queryset, "model", None)

        if model is None:
            try:
                model = view.get_queryset().model
            except Exception:
                model = None

        return model

    def _get_action_model(self, view, action, model):
        """Return the model the action creates, allowing views to declare
        per-action targets for child/collection creates."""
        action_models = getattr(view, "action_create_models", None)
        if not isinstance(action_models, dict):
            return model
        return action_models.get(action, model)

    def _has_add_model_permission(self, user, view):
        """Return whether ``user`` may create records for ``view``'s model."""
        model = self._get_view_model(view)
        return self._has_add_permission_for(user, view, "create", model)

    def _has_add_permission_for(self, user, view, action, model):
        if model is None:
            return False
        target = self._get_action_model(view, action, model)
        policy = model_policy(target)
        if policy is None:
            return False
        if policy.kind == KIND_OWNED:
            return bool(
                user
                and getattr(user, "is_authenticated", False)
                and getattr(user, "is_active", False) is True
            )
        return decide(user, "create", target).allowed

    def has_permission(self, request, view):
        """Evaluate action-level access before object-level checks run."""
        # OPTIONS only describes the endpoint; DRF's metadata class re-checks
        # permissions before advertising any write action.
        if request.method == "OPTIONS":
            return True

        # List/retrieve endpoints are publicly callable; queryset/object checks
        # enforce which records are actually visible.
        if getattr(view, "action", None) in ["list", "retrieve"]:
            return True

        model = self._get_view_model(view)
        add_permission_actions = {"create"}
        extra_add_permission_actions = getattr(
            view, "requires_add_permission_actions", None
        )
        try:
            if extra_add_permission_actions is not None:
                add_permission_actions.update(extra_add_permission_actions)
        except TypeError:
            pass

        if action in add_permission_actions:
            return self._has_add_permission_for(request.user, view, action, model)

        if request.method in permissions.SAFE_METHODS:
            from .models import UserCreatedObject

            return not (
                model is not None
                and issubclass(model, UserCreatedObject)
                and model_policy(model) is None
            )

        if model is not None:
            policy = model_policy(model)
            from .models import UserCreatedObject

            if policy is None and issubclass(model, UserCreatedObject):
                return False
            if policy is not None and action not in OBJECT_ACTION_MAP:
                return False

        return bool(
            request.user
            and getattr(request.user, "is_authenticated", False)
            and getattr(request.user, "is_active", False) is True
        )

    def has_object_permission(self, request, view, obj):
        """Evaluate object-level access via the shared policy core."""
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            return decide(user, "read", obj).allowed

        if request.method in ("PUT", "PATCH"):
            try:
                payload = request.data
            except drf_exceptions.UnsupportedMediaType:
                payload = {}
            except Exception:
                payload = {}
            if isinstance(payload, dict) and (
                _forbidden_write_fields(type(obj)) & set(payload.keys())
            ):
                return False
            return decide(user, "edit", obj).allowed

        if request.method == "DELETE":
            return decide(user, "delete", obj).allowed

        action = getattr(view, "action", None)
        policy_action = OBJECT_ACTION_MAP.get(action)
        if policy_action is not None:
            return decide(user, policy_action, obj).allowed

        return False

    def is_editor(self, user, obj):
        """Whether ``user`` holds a direct or group editor grant on ``obj``."""
        return is_editor(user, obj)

    def is_moderator(self, user, obj):
        """Whether ``user`` may moderate the model type of ``obj``."""
        return is_moderator(user, type(obj))

    def _action_allowed(self, request, obj, action):
        return decide(getattr(request, "user", None), action, obj).allowed

    def has_transfer_ownership_permission(self, request, obj):
        return self._action_allowed(request, obj, "transfer_ownership")

    def has_manage_editors_permission(self, request, obj):
        return self._action_allowed(request, obj, "manage_editors")

    def has_submit_permission(self, request, obj):
        return self._action_allowed(request, obj, "submit")

    def has_withdraw_permission(self, request, obj):
        return self._action_allowed(request, obj, "withdraw")

    def has_approve_permission(self, request, obj):
        return self._action_allowed(request, obj, "approve")

    def has_reject_permission(self, request, obj):
        return self._action_allowed(request, obj, "reject")

    def has_comment_permission(self, request, obj):
        return self._action_allowed(request, obj, "comment_on_review")

    def has_archive_permission(self, request, obj):
        return self._action_allowed(request, obj, "archive")


def _status_flags(obj):
    flags = {
        "is_private": bool(getattr(obj, "is_private", False)),
        "is_in_review": bool(getattr(obj, "is_in_review", False)),
        "is_published": bool(getattr(obj, "is_published", False)),
        "is_declined": bool(getattr(obj, "is_declined", False)),
        "is_archived": bool(getattr(obj, "is_archived", False)),
    }
    status = getattr(obj, "publication_status", None)
    mapping = {
        "private": "is_private",
        "review": "is_in_review",
        "published": "is_published",
        "declined": "is_declined",
        "archived": "is_archived",
    }
    key = mapping.get(status)
    if key is not None:
        flags[key] = True
    return flags


def _can_add_property(user, obj, caps):
    """Whether ``user`` may add a property/evidence record under ``obj``.

    Maps the core create decision: owned children delegate to parent edit,
    independent evidence children apply the attachment rule (own add
    capability + parent read + published parent or parent edit).
    """
    meta = type(obj)._meta
    child_label = _PROPERTY_CHILD_LABEL.get((meta.app_label, meta.model_name))
    if child_label is None:
        return caps["edit"].allowed
    child_model = apps.get_model(child_label)
    if child_model is None or model_policy(child_model) is None:
        return False
    return decide(user, "create", child_model, parent=obj).allowed


def get_object_policy(user, obj, request=None, review_mode=False):
    """Compute the shared policy dictionary for templates and helpers.

    All capability keys delegate to ``policy.capabilities``/``decide`` so HTML,
    API, and background consumers share one authorization contract. ``is_staff``
    reports the user's actual flag only and never implies access. URL presence
    is exposed as presentation data (``has_update_url``/``has_delete_url``) and
    does not affect decisions.
    """
    policy_entry = model_policy(type(obj))
    target = obj
    invalid_generated = False
    record = record_policy(obj)
    if record is not None and record.kind == KIND_GENERATED:
        # Generated projections display the governance surface of their
        # validated source (owner, editors, lifecycle, revision); capability
        # decisions below still run on the projection itself so every
        # standalone mutation stays denied. Invalid provenance advertises
        # nothing: copied metadata is stale compatibility data only.
        target = review_target(obj)
        if target is None:
            invalid_generated = True
            target = obj
    elif policy_entry is not None and policy_entry.kind == KIND_OWNED:
        target = resolve_parent(obj, policy_entry.parent_path) or obj

    caps = capabilities(user, obj)
    reason_codes = {action: decision.reason for action, decision in caps.items()}

    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    is_staff_flag = bool(getattr(user, "is_staff", False))
    is_owner_flag = (
        is_owner(user, target)
        if policy_entry is not None and not invalid_generated
        else False
    )
    try:
        is_editor_flag = bool(
            is_authenticated
            and not is_owner_flag
            and not invalid_generated
            and is_editor(user, target)
        )
    except Exception:
        logger.exception(
            "Failed checking editor permission in get_object_policy", exc_info=True
        )
        is_editor_flag = False

    flags = _status_flags(target)
    if invalid_generated:
        flags = dict.fromkeys(flags, False)

    try:
        is_moderator_flag = is_moderator(user, type(target))
    except Exception:
        logger.exception(
            "Failed checking moderator permission in get_object_policy",
            exc_info=True,
        )
        is_moderator_flag = False

    try:
        admin_flag = is_admin(user)
    except Exception:
        logger.exception(
            "Failed checking admin permission in get_object_policy", exc_info=True
        )
        admin_flag = False

    try:
        _meta = target.__class__._meta
        change_perm = f"{_meta.app_label}.change_{_meta.model_name}"
        has_change_permission = bool(is_authenticated and user.has_perm(change_perm))
    except Exception:
        logger.exception(
            "Failed checking change permission in get_object_policy", exc_info=True
        )
        has_change_permission = False

    has_update_url = bool(getattr(obj, "update_url", None))
    has_delete_url = bool(
        getattr(obj, "modal_delete_url", None) or getattr(obj, "delete_url", None)
    )

    can_export = caps["export"].allowed
    if flags["is_published"]:
        export_list_type = "published"
    elif flags["is_archived"]:
        export_list_type = "archived"
    else:
        export_list_type = "private" if can_export else None

    has_review_feedback = bool(
        is_owner_flag and getattr(target, "has_review_feedback", False)
    )
    review_feedback_label = (
        "Review feedback" if flags["is_declined"] else "Review activity"
    )
    can_view_review_feedback = bool(
        is_owner_flag
        and (flags["is_declined"] or has_review_feedback)
        and (not bool(review_mode))
    )

    return {
        "is_authenticated": is_authenticated,
        "is_owner": is_owner_flag,
        "is_editor": is_editor_flag,
        "is_staff": is_staff_flag,
        "is_admin": admin_flag,
        "is_moderator": is_moderator_flag,
        **flags,
        "has_change_permission": has_change_permission,
        "has_update_url": has_update_url,
        "has_delete_url": has_delete_url,
        "can_read": caps["read"].allowed,
        "can_edit": caps["edit"].allowed,
        "can_transfer_ownership": caps["transfer_ownership"].allowed,
        "can_manage_editors": caps["manage_editors"].allowed,
        "can_manage_samples": caps["edit"].allowed,
        "can_add_property": _can_add_property(user, target, caps),
        "can_duplicate": caps["duplicate"].allowed,
        "can_new_version": caps["new_version"].allowed,
        "can_archive": caps["archive"].allowed,
        "can_delete": caps["delete"].allowed,
        "can_submit_review": caps["submit"].allowed,
        "can_withdraw_review": caps["withdraw"].allowed,
        "can_approve": caps["approve"].allowed,
        "can_reject": caps["reject"].allowed,
        "can_view_review_activity": caps["view_review_activity"].allowed,
        "can_comment_on_review": caps["comment_on_review"].allowed,
        "can_export": can_export,
        "export_list_type": export_list_type,
        "has_review_feedback": has_review_feedback,
        "review_feedback_label": review_feedback_label,
        "can_view_review_feedback": can_view_review_feedback,
        "reason_codes": reason_codes,
    }


def user_is_moderator_for_model(user, model_class):
    """Return ``True`` when ``user`` may moderate ``model_class``.

    Covers users holding ``can_moderate_<model>`` and administrators; the raw
    ``is_staff`` flag alone no longer implies moderation rights.
    """
    return is_admin(user) or is_moderator(user, model_class)


def _resolve_status_value(model, status_name: str):
    """Return the concrete value for ``STATUS_<status_name>`` on the model hierarchy."""

    attr_name = f"STATUS_{status_name.upper()}"
    if hasattr(model, attr_name):
        return getattr(model, attr_name)

    from .models import UserCreatedObject

    if hasattr(UserCreatedObject, attr_name):
        return getattr(UserCreatedObject, attr_name)

    return status_name.lower()


def apply_scope_filter(queryset, scope: str | None, user=None):
    """Apply visibility scope filtering to ``queryset``.

    Delegates to ``policy.scope_queryset`` so API, HTML, and export paths share
    identical rules. ``scope=None`` applies general read visibility; an unknown
    scope returns no rows.
    """
    model = queryset.model
    if not hasattr(model, "publication_status") and model_policy(model) is None:
        raise ImproperlyConfigured(
            f"{model.__name__} must define a 'publication_status' field to use scoped lists."
        )

    return scope_queryset(user, queryset, scope)


def filter_queryset_for_user(queryset, user):
    """Return the subset of ``queryset`` visible to ``user`` under read policy."""
    return visible_queryset(user, queryset)


def visible_related_object(obj, user):
    """Return ``obj`` when ``user`` may see it under read policy, else None."""
    if obj is None:
        return None
    return obj if decide(user, "read", obj).allowed else None


def build_scope_filter_params(scope: str | None, user):
    """Return list-valued filter kwargs for export endpoints.

    These parameters are merged into URL-query-like payloads consumed by
    filtersets in async export tasks. The ``private``/``owned``/``shared``
    scopes contribute no parameters: owner and editor-grant visibility is
    enforced by ``apply_scope_filter`` on the task's base queryset.
    """
    from .models import UserCreatedObject

    if scope in ("private", "owned", "shared"):
        return {}

    if scope in ("review", "declined", "archived"):
        return {"publication_status": [_resolve_status_value(UserCreatedObject, scope)]}

    return {
        "publication_status": [_resolve_status_value(UserCreatedObject, "published")]
    }
