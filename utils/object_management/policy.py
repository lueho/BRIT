from dataclasses import dataclass

from django.db.models import Model, Q

from .registry import (
    KIND_GENERATED,
    KIND_OWNED,
    KIND_PUBLIC_CATALOGUE,
    KIND_REVIEWABLE,
    generated_profile,
    generated_source,
    model_policy,
    record_policy,
    resolve_parent,
    resolve_parents,
    root_model,
)

ADMINISTER_OBJECTS_PERMISSION = "object_management.administer_objects"

# Keep this module free of model imports: it is pulled in during settings
# load via brit.celery -> utils.file_export.generic_tasks -> permissions.
# Model-level constants mirror UserCreatedObject.STATUS_* literally.
_STATUS_PRIVATE = "private"
_STATUS_REVIEW = "review"
_STATUS_PUBLISHED = "published"
_STATUS_DECLINED = "declined"
_STATUS_ARCHIVED = "archived"

_KNOWN_STATES = frozenset(
    {
        _STATUS_PRIVATE,
        _STATUS_REVIEW,
        _STATUS_PUBLISHED,
        _STATUS_DECLINED,
        _STATUS_ARCHIVED,
    }
)

# Retained, previously published content is public historical data: frozen
# for writes, readable and exportable by every actor. Explicit ``published``
# scopes still mean active published only.
PUBLIC_READ_STATES = (_STATUS_PUBLISHED, _STATUS_ARCHIVED)
_EDITABLE_STATES = frozenset({_STATUS_PRIVATE, _STATUS_REVIEW, _STATUS_DECLINED})
_FROZEN_STATES = frozenset({_STATUS_PUBLISHED, _STATUS_ARCHIVED})
_MODERATED_STATES = frozenset({_STATUS_REVIEW, _STATUS_DECLINED})

CLASS_ACTIONS = ("create", "list")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class _Actor:
    user: object
    pk: object
    active: bool
    admin: bool


@dataclass(frozen=True)
class _Context:
    model: type
    status: str
    owner: bool
    editor: bool
    moderator: bool
    obj: object = None


_ALLOWED = Decision(True, "allowed")


def _denied(reason):
    return Decision(False, reason)


def _is_supported_parent(parent):
    if isinstance(parent, type):
        return False
    if isinstance(parent, (list, tuple)):
        return all(_is_supported_parent(p) for p in parent)
    return model_policy(type(parent)) is not None


def _has_perm(user, permission):
    checker = getattr(user, "has_perm", None)
    if not callable(checker):
        return False
    try:
        return bool(checker(permission))
    except Exception:
        return False


def _model_permission(model, action):
    return f"{model._meta.app_label}.{action}_{model._meta.model_name}"


def _actor(user):
    authenticated = bool(getattr(user, "is_authenticated", False))
    active = authenticated and getattr(user, "is_active", False) is True
    admin = bool(
        active
        and (
            getattr(user, "is_superuser", False) is True
            or _has_perm(user, ADMINISTER_OBJECTS_PERMISSION)
        )
    )
    return _Actor(user=user, pk=getattr(user, "pk", None), active=active, admin=admin)


def is_active_actor(user):
    """Whether ``user`` is an authenticated, active account."""
    return _actor(user).active


def is_admin(user):
    """Whether ``user`` is an administrator (active superuser or holder of
    ``object_management.administer_objects``). The Django staff flag alone
    never grants this status."""
    return _actor(user).admin


def is_moderator(user, model):
    """Whether ``user`` holds ``can_moderate_<model>`` for a registered model."""
    if model_policy(model) is None:
        return False
    actor = _actor(user)
    return actor.active and _has_perm(
        actor.user, _model_permission(model, "can_moderate")
    )


def is_editor(user, obj):
    """Whether ``user`` holds a direct or group editor grant on ``obj``."""
    return _is_object_editor(_actor(user), obj)


def is_owner(user, obj):
    """Whether ``user`` is the recorded owner of ``obj``."""
    actor = _actor(user)
    return bool(
        actor.active
        and actor.pk is not None
        and getattr(obj, "owner_id", None) == actor.pk
    )


def object_access_routes(user, obj):
    """Describe the actor's own access routes to ``obj``.

    Returns a list of human-readable route labels (e.g. ``"owner"``,
    ``"direct edit grant"``, ``"edit grant via group 'X'"``). Only the
    requesting actor's routes are reported; other users' grants and
    memberships are never exposed.
    """
    policy = record_policy(obj)
    generated = policy is not None and policy.kind == KIND_GENERATED
    if generated:
        source = generated_source(obj)
        if source is None:
            # Invalid provenance: copied owner/status metadata is not
            # governance and every actor is denied — report no access route.
            return ["generated value (read-only; invalid source)"]
        obj = source
    elif policy is not None and policy.kind == KIND_OWNED:
        parent = resolve_parent(obj, policy.parent_path)
        if parent is not None:
            obj = parent

    public_routes = []
    if getattr(obj, "publication_status", None) == "published":
        public_routes.append("published (public read)")
    if getattr(obj, "publication_status", None) == "archived":
        public_routes.append("archived (public historical read)")

    routes = []
    actor = _actor(user)
    if not actor.active:
        return public_routes
    if actor.admin:
        routes.append("administrator")
    if is_owner(user, obj):
        routes.append("owner")
    if actor.pk is not None and hasattr(obj, "editors"):
        try:
            if obj.editors.filter(pk=actor.pk).exists():
                routes.append("direct edit grant")
        except Exception:
            pass
        try:
            for name in (
                obj.editor_groups.filter(user=user)
                .order_by("name")
                .values_list("name", flat=True)
            ):
                routes.append(f"edit grant via group '{name}'")
        except Exception:
            pass
    if is_moderator(user, type(obj)):
        routes.append("moderator")
    routes.extend(public_routes)
    if not routes:
        routes.append("read access")
    if generated:
        routes.append("generated value (read-only; governed by source evidence)")
    return routes


EDITOR_GRANTS_VERSION_KEY = "object_management:editor_grants_version"
_UNVERSIONED = object()


def _editor_grants_version():
    import uuid

    from django.core.cache import cache

    try:
        version = cache.get(EDITOR_GRANTS_VERSION_KEY)
        if version is None:
            cache.add(EDITOR_GRANTS_VERSION_KEY, uuid.uuid4().hex, None)
            version = cache.get(EDITOR_GRANTS_VERSION_KEY)
    except Exception:
        return _UNVERSIONED
    # An unreadable version store must not freeze cached grants.
    return _UNVERSIONED if version is None else version


def invalidate_editor_grant_caches():
    """Invalidate every per-user editor-grant cache after a grant or
    group-membership change, including on user instances already held."""
    import uuid

    from django.core.cache import cache

    try:
        cache.set(EDITOR_GRANTS_VERSION_KEY, uuid.uuid4().hex, None)
    except Exception:
        pass


def _editor_grant_ids(model, user):
    from django.contrib.contenttypes.models import ContentType

    from ..transaction_scope import current_scope
    from .models import editor_grant_object_ids

    content_type = ContentType.objects.get_for_model(model)
    version = _editor_grants_version()
    if version is _UNVERSIONED:
        return set(editor_grant_object_ids(model, user))
    # The transaction scope keeps grants read inside an atomic block from
    # outliving its rollback.
    stamp = (version, current_scope())
    cache = getattr(user, "_policy_editor_grant_cache", None)
    if not isinstance(cache, dict) or cache.get("stamp") != stamp:
        cache = {"stamp": stamp, "ids": {}}
        try:
            user._policy_editor_grant_cache = cache
        except Exception:
            pass
    ids = cache["ids"].get(content_type.pk)
    if ids is None:
        ids = set(editor_grant_object_ids(model, user))
        cache["ids"][content_type.pk] = ids
    return ids


def _is_object_editor(actor, obj):
    if not actor.active or actor.pk is None or obj.pk is None:
        return False
    try:
        return obj.pk in _editor_grant_ids(type(obj), actor.user)
    except Exception:
        return False


def _context(actor, obj):
    model = type(obj)
    owner = (
        actor.active
        and actor.pk is not None
        and getattr(obj, "owner_id", None) == actor.pk
    )
    moderator = actor.active and _has_perm(
        actor.user, _model_permission(model, "can_moderate")
    )
    return _Context(
        model=model,
        status=getattr(obj, "publication_status", None),
        owner=owner,
        editor=_is_object_editor(actor, obj),
        moderator=moderator,
        obj=obj,
    )


def _content_state_gate(ctx, allowed_states):
    if ctx.status in allowed_states:
        return _ALLOWED
    if ctx.status in _FROZEN_STATES:
        return _denied("immutable_state")
    return _denied("invalid_state")


def _decide_read(actor, ctx):
    if ctx.status in PUBLIC_READ_STATES:
        return _ALLOWED
    if not actor.active:
        return _denied("authentication_required")
    if actor.admin or ctx.owner or ctx.editor:
        return _ALLOWED
    if ctx.moderator and ctx.status in _MODERATED_STATES:
        return _ALLOWED
    return _denied("no_object_access")


def _decide_edit(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if not _has_perm(actor.user, _model_permission(ctx.model, "change")):
        return _denied("missing_model_permission")
    if not (actor.admin or ctx.owner or ctx.editor):
        return _denied("no_object_access")
    return _content_state_gate(ctx, _EDITABLE_STATES)


def _decide_delete(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if not _has_perm(actor.user, _model_permission(ctx.model, "delete")):
        return _denied("missing_model_permission")
    if not (actor.admin or ctx.owner):
        return _denied("no_object_access")
    return _content_state_gate(ctx, frozenset({_STATUS_PRIVATE, _STATUS_DECLINED}))


def _decide_duplicate(actor, ctx):
    read = _decide_read(actor, ctx)
    if not read.allowed:
        return read
    if not actor.active:
        return _denied("authentication_required")
    if not _has_perm(actor.user, _model_permission(ctx.model, "add")):
        return _denied("missing_model_permission")
    return _ALLOWED


def _decide_new_version(actor, ctx):
    decision = _decide_duplicate(actor, ctx)
    if not decision.allowed:
        return decision
    if ctx.status == _STATUS_ARCHIVED:
        return _denied("immutable_state")
    return _ALLOWED


def _owner_or_admin(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if not (actor.admin or ctx.owner):
        return _denied("no_object_access")
    return _ALLOWED


def _decide_submit(actor, ctx):
    access = _owner_or_admin(actor, ctx)
    if not access.allowed:
        return access
    if ctx.status not in (_STATUS_PRIVATE, _STATUS_DECLINED):
        return _denied("invalid_state")
    return _ALLOWED


def _decide_withdraw(actor, ctx):
    access = _owner_or_admin(actor, ctx)
    if not access.allowed:
        return access
    if ctx.status not in (_STATUS_REVIEW, _STATUS_DECLINED):
        return _denied("invalid_state")
    return _ALLOWED


def _decide_review_resolution(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if not (actor.admin or ctx.moderator):
        return _denied("missing_model_permission")
    if ctx.status != _STATUS_REVIEW:
        return _denied("invalid_state")
    if ctx.owner:
        return _denied("four_eyes_required")
    return _ALLOWED


def _decide_approve(actor, ctx):
    """Approve requires review resolution rights plus four-eyes separation.

    Beyond the owner exclusion, every recorded creator or editor of the
    current candidate is excluded — contributors cannot approve their own
    content. The contributor query lives in services and is imported lazily
    to avoid an import cycle.
    """
    base = _decide_review_resolution(actor, ctx)
    if not base.allowed:
        return base
    obj = ctx.obj
    if actor.pk is None or getattr(obj, "pk", None) is None:
        # Without a stored candidate there is no contributor history to
        # check, so four-eyes separation cannot be established.
        return _denied("four_eyes_required")
    from .services import contributor_user_ids

    if actor.pk in contributor_user_ids(obj):
        return _denied("four_eyes_required")
    return _ALLOWED


def _decide_archive(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if not (actor.admin or ctx.owner or ctx.moderator):
        return _denied("no_object_access")
    if ctx.status != _STATUS_PUBLISHED:
        return _denied("invalid_state")
    return _ALLOWED


def _decide_review_participation(actor, ctx):
    if not actor.active:
        return _denied("authentication_required")
    if actor.admin or ctx.owner or ctx.editor:
        return _ALLOWED
    if ctx.moderator and _decide_read(actor, ctx).allowed:
        return _ALLOWED
    return _denied("no_object_access")


_CHECK_URL_MODELS = frozenset({"bibliography.source", "waste_collection.wasteflyer"})


def _decide_check_url(actor, ctx):
    """Operational URL health checks for registered link-bearing models only.

    Requires an active actor with the model's change permission and read
    access on the target. The action only touches ``url_valid``/``url_checked``
    metadata — never content, owner, or lifecycle state.
    """
    label = ctx.model._meta.label_lower
    if label not in _CHECK_URL_MODELS:
        return _denied("unsupported_action")
    if not actor.active:
        return _denied("authentication_required")
    if not _has_perm(actor.user, _model_permission(ctx.model, "change")):
        return _denied("missing_model_permission")
    return _decide_read(actor, ctx)


_OBJECT_ACTION_HANDLERS = {
    "read": _decide_read,
    "export": _decide_read,
    "edit": _decide_edit,
    "delete": _decide_delete,
    "duplicate": _decide_duplicate,
    "new_version": _decide_new_version,
    "submit": _decide_submit,
    "withdraw": _decide_withdraw,
    "approve": _decide_approve,
    "reject": _decide_review_resolution,
    "archive": _decide_archive,
    "view_review_activity": _decide_review_participation,
    "comment_on_review": _decide_review_participation,
    "manage_editors": _owner_or_admin,
    "transfer_ownership": _owner_or_admin,
    "check_url": _decide_check_url,
}

OBJECT_ACTIONS = tuple(_OBJECT_ACTION_HANDLERS)


def _decide_create(actor, model):
    if not actor.active:
        return _denied("authentication_required")
    if not _has_perm(actor.user, _model_permission(model, "add")):
        return _denied("missing_model_permission")
    return _ALLOWED


def _parent_attachment_gate(actor, parent, policy):
    """Typed attachment eligibility of ``parent`` for one evidence row.

    Unpublished parents require edit access; published and archived parents
    accept attachments according to the model's declared
    ``published_attachment`` scope (``read`` allows any reader,
    ``collaborator`` requires owner/editor/admin access to the parent).
    Visibility alone never grants write access.
    """
    ctx = _context(actor, parent)
    if ctx.status not in _KNOWN_STATES:
        return _denied("invalid_state")
    read = _decide_read(actor, ctx)
    if not read.allowed:
        return read
    if ctx.status in PUBLIC_READ_STATES:
        attachment = policy.published_attachment
        if attachment == "read":
            return _ALLOWED
        if attachment == "collaborator" and (actor.admin or ctx.owner or ctx.editor):
            return _ALLOWED
        return _denied("insufficient_parent_access")
    return _decide_edit(actor, ctx)


def _decide_attached_create(actor, model, policy, parents):
    """Create on a reviewable root attached to one or more parents.

    Requires the model's own add capability plus, for every supplied parent,
    the typed attachment eligibility from ``_parent_attachment_gate``.
    """
    from .models import UserCreatedObject

    root = root_model(model, policy.parent_path) if policy.parent_path else None
    if root is None:
        return _denied("invalid_parent")

    own = _decide_create(actor, model)
    if not own.allowed:
        return own
    for parent in parents:
        if (
            not isinstance(parent, root)
            or not isinstance(parent, UserCreatedObject)
            or parent.pk is None
        ):
            return _denied("invalid_parent")
        gate = _parent_attachment_gate(actor, parent, policy)
        if not gate.allowed:
            return gate
    return _ALLOWED


def decide_reassign(user, obj, parent) -> Decision:
    """Authorize reassigning a persisted attached row to new parent(s).

    Owned children require edit access on both the stored root and every
    proposed root. Independent evidence rows require edit access on the
    record itself, read access on the stored parent, and the declared typed
    attachment eligibility on each proposed parent — the model's ``add``
    capability is not required for existing rows. Unsaved, missing, or
    wrong-type parents are rejected.
    """
    policy = record_policy(obj)
    if policy is None or policy.parent_path is None:
        return _denied("unsupported_model")
    if policy.kind == KIND_GENERATED:
        return _denied("generated_projection")
    actor = _actor(user)
    if not actor.active:
        return _denied("authentication_required")
    if getattr(obj, "pk", None) is None:
        return _denied("invalid_parent")
    if isinstance(parent, Model):
        parents = (parent,)
    elif isinstance(parent, (list, tuple)):
        parents = tuple(parent)
    else:
        return _denied("invalid_parent")
    if not parents:
        return _denied("invalid_parent")
    expected_root = root_model(type(obj), policy.parent_path)
    if expected_root is None:
        return _denied("invalid_parent")
    if policy.kind == KIND_OWNED and len(parents) != 1:
        return _denied("invalid_parent")
    for candidate in parents:
        if not isinstance(candidate, expected_root) or candidate.pk is None:
            return _denied("invalid_parent")
    old_parents = resolve_parents(obj, policy.parent_path)
    if not old_parents or any(getattr(p, "pk", None) is None for p in old_parents):
        return _denied("invalid_parent")
    if policy.kind == KIND_OWNED:
        for root in (*old_parents, *parents):
            gate = _decide_edit(actor, _context(actor, root))
            if not gate.allowed:
                return gate
        return _ALLOWED
    if policy.kind != KIND_REVIEWABLE:
        return _denied("unsupported_model")
    own = _decide_edit(actor, _context(actor, obj))
    if not own.allowed:
        return own
    for stored in old_parents:
        read_old = _decide_read(actor, _context(actor, stored))
        if not read_old.allowed:
            return read_old
    for candidate in parents:
        gate = _parent_attachment_gate(actor, candidate, policy)
        if not gate.allowed:
            return gate
    return _ALLOWED


def _decide_class(actor, action, model, policy, parent):
    if action == "list":
        return _ALLOWED
    if action != "create":
        return _denied("unsupported_action")
    if policy.kind == KIND_OWNED:
        if parent is None:
            return _denied("parent_required")
        if isinstance(parent, (list, tuple)):
            return _denied("invalid_parent")
        root = root_model(model, policy.parent_path)
        if (
            root is None
            or not isinstance(parent, root)
            or getattr(parent, "pk", None) is None
        ):
            return _denied("invalid_parent")
        root_policy = model_policy(root)
        if root_policy is None or root_policy.kind != KIND_REVIEWABLE:
            return _denied("invalid_parent")
        ctx = _context(actor, parent)
        if ctx.status not in _KNOWN_STATES:
            return _denied("invalid_state")
        return _decide_edit(actor, ctx)
    if parent is not None:
        parents = (parent,) if isinstance(parent, Model) else tuple(parent)
        if not parents:
            return _denied("invalid_parent")
        return _decide_attached_create(actor, model, policy, parents)
    return _decide_create(actor, model)


def _decide_catalogue(actor, action, ctx):
    if action in ("read", "export"):
        return _ALLOWED
    if action == "edit":
        if not actor.active:
            return _denied("authentication_required")
        if not _has_perm(actor.user, _model_permission(ctx.model, "change")):
            return _denied("missing_model_permission")
        return _ALLOWED
    if action == "delete":
        if not actor.active:
            return _denied("authentication_required")
        if not _has_perm(actor.user, _model_permission(ctx.model, "delete")):
            return _denied("missing_model_permission")
        return _ALLOWED
    return _denied("unsupported_action")


_OWNED_OBJECT_ACTIONS = frozenset({"read", "export", "create", "edit", "delete"})


def _decide_owned(actor, action, obj, policy, parent):
    if action not in _OWNED_OBJECT_ACTIONS:
        return _denied("unsupported_action")
    root = resolve_parent(obj, policy.parent_path)
    if root is None:
        return _denied("invalid_parent")
    if parent is not None and parent != root:
        return _denied("invalid_parent")
    root_policy = model_policy(type(root))
    if root_policy is None or root_policy.kind != KIND_REVIEWABLE:
        return _denied("invalid_parent")
    ctx = _context(actor, root)
    if ctx.status not in _KNOWN_STATES:
        return _denied("invalid_state")
    if action in ("read", "export"):
        return _decide_read(actor, ctx)
    return _decide_edit(actor, ctx)


# Actions a generated projection delegates to its linked source evidence.
# Everything else is a standalone mutation of a read-only projection.
_GENERATED_SOURCE_ACTIONS = frozenset(
    {"read", "export", "view_review_activity", "comment_on_review"}
)


def _decide_generated(actor, action, obj, policy):
    """Decide on a generated projection via its raw source evidence.

    Read/export and review participation delegate to the source's own
    decision; its copied metadata or grants never widen access. Missing,
    cyclic, generated, or otherwise invalid provenance fails closed for
    every actor, including administrators. All standalone mutations are
    denied — users change or review the source instead.
    """
    if action not in _GENERATED_SOURCE_ACTIONS:
        return _denied("generated_projection")
    source = generated_source(obj)
    if source is None:
        return _denied("invalid_parent")
    return decide(actor.user, action, source)


def decide(user, action: str, target, *, parent=None) -> Decision:
    if isinstance(target, type):
        policy = model_policy(target)
        if policy is None:
            return _denied("unsupported_model")
        if parent is not None and not _is_supported_parent(parent):
            return _denied("unsupported_model")
        return _decide_class(_actor(user), action, target, policy, parent)
    policy = record_policy(target)
    if policy is None:
        return _denied("unsupported_model")
    if parent is not None and not _is_supported_parent(parent):
        return _denied("unsupported_model")
    actor = _actor(user)
    if policy.kind == KIND_GENERATED:
        return _decide_generated(actor, action, target, policy)
    if policy.kind == KIND_OWNED:
        return _decide_owned(actor, action, target, policy, parent)
    ctx = _context(actor, target)
    if policy.kind == KIND_PUBLIC_CATALOGUE:
        return _decide_catalogue(actor, action, ctx)
    if ctx.status not in _KNOWN_STATES:
        return _denied("invalid_state")
    handler = _OBJECT_ACTION_HANDLERS.get(action)
    if handler is None:
        return _denied("unsupported_action")
    return handler(actor, ctx)


def capabilities(user, target, *, parent=None) -> dict[str, Decision]:
    if isinstance(target, type) or model_policy(type(target)) is None:
        return {}
    return {
        action: decide(user, action, target, parent=parent) for action in OBJECT_ACTIONS
    }


def _grant_ids_subquery(model, user):
    try:
        from .models import editor_grant_object_ids

        return editor_grant_object_ids(model, user)
    except Exception:
        return []


def _reviewable_root(model, policy):
    root = root_model(model, policy.parent_path)
    if root is None:
        return None
    root_policy = model_policy(root)
    if root_policy is None or root_policy.kind != KIND_REVIEWABLE:
        return None
    return root


def _ordinary_visible(user, queryset):
    """General read visibility for raw reviewable rows.

    Retains the valid-state filter plus owner/editor/admin/moderator
    semantics and never applies generated-projection expansion.
    """
    model = queryset.model
    actor = _actor(user)
    valid = Q(publication_status__in=_KNOWN_STATES)
    if not actor.active:
        return queryset.filter(valid & Q(publication_status__in=PUBLIC_READ_STATES))
    if actor.admin:
        return queryset.filter(valid)
    visibility = Q(publication_status__in=PUBLIC_READ_STATES)
    if actor.pk is not None:
        visibility |= Q(owner_id=actor.pk)
        visibility |= Q(pk__in=_grant_ids_subquery(model, actor.user))
    if _has_perm(actor.user, _model_permission(model, "can_moderate")):
        visibility |= Q(publication_status__in=_MODERATED_STATES)
    return queryset.filter(valid & visibility)


def _generated_visible(user, queryset, ordinary):
    """Combine caller-filtered raw rows with source-governed projections.

    Generated rows are visible exactly when their explicitly linked raw
    source is visible under ``ordinary``. Source eligibility starts from
    the model's base manager so caller restrictions (property, unit, year)
    on the projection never filter out a differently typed source.
    """
    marker, pointer = generated_profile(queryset.model)
    raw_visible = ordinary(user, queryset.filter(**{marker: False}))
    source_visible = ordinary(
        user, queryset.model._base_manager.filter(**{marker: False})
    )
    generated_visible = queryset.filter(
        **{marker: True, f"{pointer}_id__in": source_visible.values("pk")}
    )
    return queryset.filter(
        Q(pk__in=raw_visible.values("pk")) | Q(pk__in=generated_visible.values("pk"))
    )


def visible_queryset(user, queryset):
    model = queryset.model
    policy = model_policy(model)
    if policy is None:
        return queryset.none()
    if policy.kind == KIND_OWNED:
        root = _reviewable_root(model, policy)
        if root is None:
            return queryset.none()
        roots = visible_queryset(user, root._base_manager.all())
        return queryset.filter(**{f"{policy.parent_path}__in": roots})
    if policy.kind == KIND_PUBLIC_CATALOGUE:
        return queryset
    if generated_profile(model) is not None:
        return _generated_visible(user, queryset, _ordinary_visible)
    return _ordinary_visible(user, queryset)


def _ordinary_scope(user, queryset, scope):
    """Scope ``queryset`` within ordinary (raw) read visibility."""
    model = queryset.model
    visible = _ordinary_visible(user, queryset)
    if scope is None:
        return visible
    if scope == "published":
        return visible.filter(publication_status=_STATUS_PUBLISHED)
    actor = _actor(user)
    if not actor.active or actor.pk is None:
        if scope in ("private", "owned", "shared"):
            return visible.none()
        if scope in (_STATUS_REVIEW, _STATUS_DECLINED, _STATUS_ARCHIVED):
            return visible.filter(publication_status=scope)
        return visible.none()
    if scope == "private":
        return visible.filter(
            Q(owner_id=actor.pk) | Q(pk__in=_grant_ids_subquery(model, actor.user))
        )
    if scope == "owned":
        return visible.filter(owner_id=actor.pk)
    if scope == "shared":
        return visible.filter(pk__in=_grant_ids_subquery(model, actor.user)).exclude(
            owner_id=actor.pk
        )
    if scope in (_STATUS_REVIEW, _STATUS_DECLINED, _STATUS_ARCHIVED):
        return visible.filter(publication_status=scope)
    return visible.none()


def scope_queryset(user, queryset, scope=None):
    model = queryset.model
    policy = model_policy(model)
    if policy is None:
        return queryset.none()
    if policy.kind == KIND_OWNED:
        root = _reviewable_root(model, policy)
        if root is None:
            return queryset.none()
        roots = scope_queryset(user, root._base_manager.all(), scope)
        return queryset.filter(**{f"{policy.parent_path}__in": roots})
    if policy.kind == KIND_PUBLIC_CATALOGUE:
        if scope in (None, "published"):
            return queryset
        return queryset.none()
    if generated_profile(model) is not None:
        return _generated_visible(
            user, queryset, lambda u, qs: _ordinary_scope(u, qs, scope)
        )
    return _ordinary_scope(user, queryset, scope)


def publication_states_queryset(user, queryset, states):
    """Literal lifecycle-state filtering over authorized visibility.

    ``states`` must be a non-empty subset of the known lifecycle values;
    unknown or empty input yields no rows. This is literal state filtering —
    ``private`` means the stored state is private, not the workspace scope.
    Generated projections carry no own lifecycle: they match when their
    linked source's status is in ``states``. Owned children resolve state
    through their declared reviewable parent.
    """
    model = queryset.model
    policy = model_policy(model)
    if policy is None:
        return queryset.none()
    requested = tuple(states or ())
    if not requested or any(state not in _KNOWN_STATES for state in requested):
        return queryset.none()
    visible = visible_queryset(user, queryset)
    if policy.kind == KIND_OWNED:
        root = _reviewable_root(model, policy)
        if root is None:
            return queryset.none()
        roots = publication_states_queryset(user, root._base_manager.all(), requested)
        return visible.filter(**{f"{policy.parent_path}__in": roots})
    profile = generated_profile(model)
    if profile is not None:
        marker, pointer = profile
        return visible.filter(
            Q(**{marker: False, "publication_status__in": requested})
            | Q(
                **{
                    marker: True,
                    f"{pointer}__publication_status__in": requested,
                }
            )
        )
    return visible.filter(publication_status__in=requested)


def editable_queryset(user, queryset):
    """Return the subset of ``queryset`` where ``user`` may edit each row.

    Mirrors the object-level ``edit`` decision: registered models only,
    editable lifecycle states, and owner/editor/admin access combined with the
    model's own ``change`` permission. Administrator status widens the scope
    but never replaces the capability requirement.
    """
    model = queryset.model
    policy = model_policy(model)
    if policy is None:
        return queryset.none()
    actor = _actor(user)
    if not actor.active:
        return queryset.none()
    if policy.kind == KIND_OWNED:
        root = _reviewable_root(model, policy)
        if root is None:
            return queryset.none()
        roots = editable_queryset(user, root._base_manager.all())
        return queryset.filter(**{f"{policy.parent_path}__in": roots})
    if not _has_perm(actor.user, _model_permission(model, "change")):
        return queryset.none()
    profile = generated_profile(model)
    if profile is not None:
        # Generated projections are read-only; only raw rows can be edited.
        queryset = queryset.filter(**{profile[0]: False})
    if policy.kind == KIND_PUBLIC_CATALOGUE:
        return queryset
    base = queryset.filter(publication_status__in=_EDITABLE_STATES)
    if actor.pk is None:
        return queryset.none()
    if actor.admin:
        return base
    return base.filter(
        Q(owner_id=actor.pk) | Q(pk__in=_grant_ids_subquery(model, actor.user))
    )


def reviewable_queryset(user, queryset):
    """Return rows of ``queryset`` the user may review (moderate).

    Restricted to records in ``review`` status for users holding the model's
    moderation permission or administrator status, excluding the user's own
    records, which four-eyes review never lets them resolve.
    """
    model = queryset.model
    policy = model_policy(model)
    if policy is None or policy.kind != KIND_REVIEWABLE:
        return queryset.none()
    actor = _actor(user)
    if not actor.active:
        return queryset.none()
    if not (
        actor.admin or _has_perm(actor.user, _model_permission(model, "can_moderate"))
    ):
        return queryset.none()
    queryset = queryset.filter(publication_status=_STATUS_REVIEW)
    if actor.pk is not None:
        # Four-eyes: own submissions can be neither approved nor rejected.
        queryset = queryset.exclude(owner_id=actor.pk)
    profile = generated_profile(model)
    if profile is not None:
        # Review queues hold raw evidence only; projections have no
        # independent approval.
        queryset = queryset.filter(**{profile[0]: False})
    return queryset
