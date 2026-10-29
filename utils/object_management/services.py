"""Shared authorized mutation, creation, and review-transition boundaries.

Migrated public adapters route content writes and lifecycle transitions for
registered models through this module; remaining domain-specific and admin
writers are tracked in the implementation map as pending migration.
``content_mutation`` locks the independently reviewable root, re-evaluates
the shared policy against freshly persisted state, and records a single
revision bump plus audit event for meaningful changes.
``perform_transition`` applies named review actions under the same lock and
binds approvals to the exact inspected ``content_revision``.

Authorization itself is never duplicated here: every boundary delegates to
``policy.decide`` and the registry's root resolution.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db import DatabaseError, router, transaction
from django.db.models import ForeignKey, Max, Model, QuerySet
from django.db.models.deletion import Collector
from django.forms.models import construct_instance
from django.utils import timezone

from .models import ReviewAction, UserCreatedObject
from .policy import decide, decide_reassign
from .registry import (
    KIND_GENERATED,
    KIND_OWNED,
    KIND_REVIEWABLE,
    OWNED_CHILDREN,
    allows_unattached_create,
    generated_profile,
    generated_source,
    model_policy,
    record_policy,
    resolve_create_parent,
    resolve_parent,
    resolve_parents,
    root_model,
)

_AUDIT_FIELD_NAMES = frozenset(
    {
        "id",
        "owner",
        "owner_id",
        "publication_status",
        "content_revision",
        "submitted_at",
        "approved_at",
        "approved_by",
        "approved_by_id",
        "created_at",
        "created_by",
        "created_by_id",
        "lastmodified_at",
        "lastmodified_by",
        "lastmodified_by_id",
        "url_valid",
        "url_checked",
        "evaluation_status",
    }
)

logger = logging.getLogger(__name__)

_TRANSITION_METHODS = {
    "submit": ("submit_for_review", ReviewAction.ACTION_SUBMITTED),
    "withdraw": ("withdraw_from_review", ReviewAction.ACTION_WITHDRAWN),
    "approve": ("approve", ReviewAction.ACTION_APPROVED),
    "reject": ("reject", ReviewAction.ACTION_REJECTED),
    "archive": ("archive", ReviewAction.ACTION_ARCHIVED),
}

_ACTIVE_MUTATION_ROOTS: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "brit_active_mutation_roots", default=None
)


class StaleRevisionError(ValidationError):
    """The caller's inspected content revision no longer matches persistence."""

    def __init__(self, expected, current):
        super().__init__(
            "The record changed since it was inspected. "
            "Reload the review page and approve again.",
            code="stale_revision",
        )
        self.expected = expected
        self.current = current


def _fresh_actor(user):
    pk = getattr(user, "pk", None)
    if pk is None:
        return user
    User = get_user_model()
    if not isinstance(user, User):
        return user
    try:
        return User.objects.get(pk=pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("The acting user account no longer exists.") from exc


def _norm(value):
    if hasattr(value, "ewkt"):
        return value.ewkt
    return value


def authorize_create(actor, model, *, parent=None):
    """Authoritative ``create`` authorization inside the write boundary.

    Resolves the registered policy, enforces the declared ``parent_path``
    context, re-reads the actor through ``_fresh_actor``, and locks every
    declared parent row via ``select_for_update`` in deterministic storage
    order — a stale permission cache, a vanished, unsaved, or wrongly typed
    parent, or a parent lifecycle transition committed since any advisory
    check can never authorize a write. Returns the fresh actor for owner
    attribution and audit writes.

    Locking the parents serializes creates against concurrent review
    transitions on the same rows (the same ``_storage_key`` ordering
    ``content_mutation`` uses, so no deadlock cycle is possible): an
    approval that commits first is re-decided against the fresh locked row,
    and one that arrives later waits until this boundary commits. Callers
    must therefore invoke this inside the atomic write boundary that
    persists the object so the locks are held through the save.

    Callers must only route registered models here; unregistered non-UCO
    persistence stays on the plain adapter path.
    """
    policy = model_policy(model)
    if policy is None:
        raise PermissionDenied("unsupported_model")
    actor = _fresh_actor(actor)
    if policy.parent_path is not None:
        if parent is None and allows_unattached_create(model):
            pass  # optional direct-FK parent legitimately omitted
        else:
            try:
                members = (
                    (parent,) if isinstance(parent, Model) else tuple(parent or ())
                )
            except TypeError:
                raise PermissionDenied("invalid_parent") from None
            if not members:
                raise PermissionDenied("Creation requires a valid parent context.")
            expected = root_model(model, policy.parent_path)
            for candidate in members:
                pk = getattr(candidate, "pk", None)
                if (
                    expected is None
                    or not isinstance(candidate, expected)
                    or pk is None
                ):
                    raise PermissionDenied("invalid_parent")
            locked = {}
            for candidate in sorted(members, key=_storage_key):
                key = _storage_key(candidate)
                if key in locked:
                    continue
                try:
                    locked[key] = _lock_instance(candidate)
                except ObjectDoesNotExist:
                    raise PermissionDenied("invalid_parent") from None
            fresh = [locked[_storage_key(candidate)] for candidate in members]
            parent = fresh[0] if isinstance(parent, Model) else tuple(fresh)
    decision = decide(actor, "create", model, parent=parent)
    if not decision.allowed:
        raise PermissionDenied(decision.reason)
    return actor


def validate_references(actor, validated_data):
    """Require read access on every referenced record in validated data.

    Traverses model instances, dicts, and list/tuple/queryset values: a
    ``UserCreatedObject`` or explicitly policy-registered instance is
    re-fetched via ``_base_manager`` — a stale instance whose access was
    revoked, an unsaved row, or a deleted row fails closed with
    ``PermissionDenied`` — and then must satisfy ``decide(actor, "read")``.
    Scalar and unregistered non-UCO values pass through. Foreign keys are
    enforced on the resolved instances, never inferred from raw ids.
    """

    def visit(value):
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple, QuerySet)):
            for item in value:
                visit(item)
        elif isinstance(value, Model) and (
            isinstance(value, UserCreatedObject)
            or model_policy(type(value)) is not None
        ):
            fresh = type(value)._base_manager.filter(pk=value.pk).first()
            if fresh is None:
                raise PermissionDenied("inaccessible_reference")
            if not decide(actor, "read", fresh).allowed:
                raise PermissionDenied("inaccessible_reference")

    if isinstance(validated_data, dict):
        for item in validated_data.values():
            visit(item)
    else:
        visit(validated_data)


def validate_created_parent(obj, *, parent):
    """Assert the persisted row's declared parents equal the authorized
    context.

    Runs after actual persistence inside the same atomic write: a serializer
    or form that stored a different parent than the authorized one fails
    closed and rolls the whole write back. Identity uses the ``_storage_key``
    normalization so proxy/MTI aliases cannot fake a match.
    """
    policy = model_policy(type(obj))
    if policy is None or policy.parent_path is None:
        return
    if getattr(obj, "pk", None) is None:
        return  # advisory preflight path; nothing persisted to compare
    persisted = type(obj)._base_manager.filter(pk=obj.pk).first()
    if persisted is None:
        raise PermissionDenied("invalid_parent")
    if parent is None:
        if not allows_unattached_create(type(obj)):
            raise PermissionDenied("invalid_parent")
        fk_field = type(obj)._meta.get_field(policy.parent_path)
        if getattr(persisted, fk_field.attname) is not None:
            raise PermissionDenied("invalid_parent")
        return
    actual = {_storage_key(p) for p in resolve_parents(persisted, policy.parent_path)}
    members = (parent,) if isinstance(parent, Model) else tuple(parent)
    expected = {_storage_key(p) for p in members}
    if not actual or actual != expected:
        raise PermissionDenied("invalid_parent")


def _row_snapshot(obj):
    data = {}
    for field in obj._meta.get_fields():
        if field.auto_created and not field.concrete:
            continue
        if field.many_to_many:
            data[f"m2m.{field.name}"] = tuple(
                sorted(getattr(obj, field.name).values_list("pk", flat=True))
            )
        elif field.concrete and not field.primary_key:
            name = field.attname
            if field.name in _AUDIT_FIELD_NAMES or name in _AUDIT_FIELD_NAMES:
                continue
            key = field.name
            data[key] = _norm(getattr(obj, name))
    return data


def _owned_child_models(root_cls):
    for label, path in OWNED_CHILDREN.items():
        child = apps.get_model(label)
        if child is None:
            continue
        resolved = root_model(child, path)
        if resolved is None:
            continue
        if (
            resolved is root_cls
            or resolved._meta.concrete_model is root_cls._meta.concrete_model
            or root_cls in resolved._meta.get_parent_list()
            or resolved in root_cls._meta.get_parent_list()
        ):
            yield child, label, path


def _content_snapshot(root):
    snapshot = {"": _row_snapshot(root)}
    for child, label, path in _owned_child_models(type(root)):
        for row in child._base_manager.filter(**{path: root}):
            snapshot[f"{label}#{row.pk}"] = _row_snapshot(row)
    return snapshot


def _diff_snapshots(before, after):
    changed = set()
    for key in before.keys() | after.keys():
        old, new = before.get(key), after.get(key)
        if key and old is None:
            changed.add(f"{key}:created")
            continue
        if key and new is None:
            changed.add(f"{key}:deleted")
            continue
        if old is None or new is None:
            continue
        for field in sorted(set(old) | set(new)):
            if old.get(field) != new.get(field):
                changed.add(field if key == "" else f"{key}.{field}")
    return sorted(changed)


def _facet_models(model):
    models = {model}
    models.update(model._meta.get_parent_list())
    for candidate in apps.get_models():
        if model in candidate._meta.get_parent_list():
            models.add(candidate)
    return {m for m in models if model_policy(m) is not None}


def _facet_content_types(model):
    return [ContentType.objects.get_for_model(facet) for facet in _facet_models(model)]


def _review_actions_for_root(root):
    return ReviewAction.objects.filter(
        content_type__in=_facet_content_types(type(root)), object_id=root.pk
    )


def contributor_user_ids(root):
    """Users who created or meaningfully edited this root's current candidate.

    Recorded ``created``/``edited`` events are combined with the root's
    ``created_by``/``lastmodified_by`` metadata, so an edit saved without an
    audit event still excludes its author from approval.
    """
    contributors = set(
        _review_actions_for_root(root)
        .filter(
            action__in=(
                ReviewAction.ACTION_CREATED,
                ReviewAction.ACTION_EDITED,
            )
        )
        .values_list("user_id", flat=True)
    )
    for field in ("created_by_id", "lastmodified_by_id"):
        user_id = getattr(root, field, None)
        if user_id is not None:
            contributors.add(user_id)
    return contributors


def last_reviewed_revision(user, root):
    """Highest content revision this user verifiably inspected.

    Only revision-bound comments and successful revision-bound approvals
    count as proof of inspection; lifecycle events (created, edited,
    submitted, withdrawn, rejected, archived) are bound to the revision they
    operated on but never establish a review watermark.
    """
    if getattr(user, "pk", None) is None:
        return None
    return (
        _review_actions_for_root(root)
        .filter(
            user_id=user.pk,
            action__in=(
                ReviewAction.ACTION_COMMENT,
                ReviewAction.ACTION_APPROVED,
            ),
        )
        .exclude(content_revision__isnull=True)
        .aggregate(Max("content_revision"))["content_revision__max"]
    )


def _storage_key_for(model, pk):
    """Canonical physical counter identity for a governed record.

    Proxy and multi-table facets share the declaring table of the
    ``content_revision`` field, so facet views of one persisted record map to
    the same identity.
    """
    try:
        field_model = model._meta.get_field("content_revision").model
    except Exception:
        field_model = model
    return (field_model._meta.label_lower, pk)


def _storage_key(obj):
    return _storage_key_for(type(obj), obj.pk)


_PROTECTED_MUTATION_ATTNAMES = frozenset(
    {
        "owner_id",
        "publication_status",
        "content_revision",
        "submitted_at",
        "approved_at",
        "approved_by_id",
        "created_at",
        "created_by_id",
        "is_derived",
        "derived_from_id",
    }
)


def _protected_metadata(obj):
    values = {}
    for field in obj._meta.fields:
        if field.attname in _PROTECTED_MUTATION_ATTNAMES:
            values[field.attname] = getattr(obj, field.attname)
    return values


def _lock_instance(obj):
    model = type(obj)
    for parent in model._meta.get_parent_list():
        parent._base_manager.select_for_update().get(pk=obj.pk)
    return model._base_manager.select_for_update().get(pk=obj.pk)


def _record_event(
    root, actor, action, *, content_revision, changed_fields, comment="", object_id=None
):
    return ReviewAction.objects.create(
        content_type=ContentType.objects.get_for_model(type(root)),
        object_id=root.pk if object_id is None else object_id,
        user=actor,
        action=action,
        comment=comment or "",
        content_revision=content_revision,
        changed_fields=list(changed_fields),
    )


def _finalize_mutation(
    actor, locked_root, root_pk, protected_before, before, action, disposition
):
    manager = type(locked_root)._base_manager
    still_exists = manager.filter(pk=root_pk).exists()
    if not still_exists:
        # A nested ``delete`` mutation may remove an outer-tracked root; only
        # an authorized deletion is recorded, an edit callback may not delete.
        if action != "delete" and not disposition["deleted"]:
            raise PermissionDenied("A content edit may not delete the record.")
        _record_event(
            locked_root,
            disposition["deleted_by"] or actor,
            ReviewAction.ACTION_DELETED,
            object_id=root_pk,
            content_revision=locked_root.content_revision,
            changed_fields=["deleted"],
        )
        return

    locked_root.refresh_from_db()
    tampered = [
        name
        for name, old in protected_before.items()
        if _norm(getattr(locked_root, name, None)) != _norm(old)
    ]
    if tampered:
        raise PermissionDenied(
            "A content edit may not change protected record metadata."
        )
    after = _content_snapshot(locked_root)
    changed = _diff_snapshots(before, after)
    if not changed:
        return
    locked_root.content_revision = (locked_root.content_revision or 0) + 1
    locked_root.lastmodified_at = timezone.now()
    locked_root.lastmodified_by = actor if getattr(actor, "pk", None) else None
    locked_root.save(
        update_fields=["content_revision", "lastmodified_at", "lastmodified_by"]
    )
    _record_event(
        locked_root,
        actor,
        ReviewAction.ACTION_EDITED,
        content_revision=locked_root.content_revision,
        changed_fields=changed,
    )


_DELETE_BOUNDARY_MESSAGE = "Deletion crosses the boundary of another governed record."


def _check_through_row(instance, root_key, deleted_keys):
    """Deny when an auto-created M2M row belongs to a foreign governed root.

    The row belongs to the model that declared the relation
    (``_meta.auto_created``). Removing rows owned by a record that is itself
    inside this delete boundary is fine; unlinking a different governed root
    is not.
    """
    owner_model = getattr(type(instance)._meta, "auto_created", None)
    owner_fks = [
        field
        for field in instance._meta.fields
        if isinstance(field, ForeignKey) and field.remote_field.model is owner_model
    ]
    owner_field = next(
        (field for field in owner_fks if field.name.startswith("from_")),
        owner_fks[0] if owner_fks else None,
    )
    if owner_field is None:
        return
    owner_key = _storage_key_for(owner_model, owner_field.value_from_object(instance))
    if owner_key in deleted_keys:
        return
    if model_policy(owner_model) is not None or (
        isinstance(owner_model, type) and issubclass(owner_model, UserCreatedObject)
    ):
        raise PermissionDenied(_DELETE_BOUNDARY_MESSAGE)


def _check_collected_row(model, instance, root, root_key, deleted_keys=None):
    pk = getattr(instance, "pk", instance)
    if _storage_key_for(model, pk) == root_key:
        return
    policy = model_policy(model)
    if policy is None:
        if issubclass(model, UserCreatedObject):
            raise PermissionDenied(_DELETE_BOUNDARY_MESSAGE)
        return
    profile = generated_profile(model)
    if profile is not None:
        marker, pointer = profile
        if not isinstance(instance, model):
            instance = model._base_manager.get(pk=pk)
        if getattr(instance, marker, False):
            # A generated dependant may be deleted only alongside the raw
            # source it explicitly points to — never on its own, and never
            # crossing another source root.
            source_pk = getattr(instance, f"{pointer}_id", None)
            if source_pk is not None and deleted_keys is not None:
                source_model = model._meta.get_field(pointer).remote_field.model
                source_key = _storage_key_for(source_model, source_pk)
                if source_key in deleted_keys:
                    return
            raise PermissionDenied(_DELETE_BOUNDARY_MESSAGE)
    if policy.kind == KIND_REVIEWABLE:
        raise PermissionDenied(_DELETE_BOUNDARY_MESSAGE)
    if policy.kind == KIND_OWNED:
        if not isinstance(instance, model):
            instance = model._base_manager.get(pk=pk)
        other_root = resolve_parent(instance, policy.parent_path)
        if other_root is None or _storage_key(other_root) != root_key:
            raise PermissionDenied(_DELETE_BOUNDARY_MESSAGE)


def _check_delete_cascade(target, root):
    collector = Collector(using=router.db_for_write(type(target)))
    collector.collect([target])
    root_key = _storage_key(root)
    deleted_keys = {
        _storage_key_for(model, getattr(instance, "pk", instance))
        for model, instances in collector.data.items()
        for instance in instances
    }
    for queryset in collector.fast_deletes:
        for instance in queryset:
            if getattr(type(instance)._meta, "auto_created", False):
                _check_through_row(instance, root_key, deleted_keys)
            else:
                _check_collected_row(
                    type(instance), instance, root, root_key, deleted_keys
                )
    for model, instances in collector.data.items():
        if getattr(model._meta, "auto_created", False):
            for instance in instances:
                _check_through_row(instance, root_key, deleted_keys)
            continue
        for instance in instances:
            _check_collected_row(model, instance, root, root_key, deleted_keys)
    for (field, _value), instance_lists in collector.field_updates.items():
        model = field.model
        if getattr(model._meta, "auto_created", False):
            for instances in instance_lists:
                for instance in instances:
                    _check_through_row(instance, root_key, deleted_keys)
            continue
        for instances in instance_lists:
            for instance in instances:
                _check_collected_row(model, instance, root, root_key, deleted_keys)


@contextmanager
def content_mutation(
    actor, target, *, action: str = "edit", parent=None, proposed_parent=None
) -> Iterator[object]:
    """Lock, authorize, and audit one content mutation on a registry root.

    Yields the freshly loaded, locked target row. For owned children the
    stored parent is resolved, locked, and then re-resolved on the locked
    row so a concurrent reparent or publication can never authorize a write
    against a stale parent snapshot. With ``proposed_parent`` the mutation
    is a reassignment: every affected root (stored parent, proposed
    parents, and the record's own root for independent evidence) is locked
    in deterministic storage order, re-checked, and audited while the locks
    remain held through the callback.

    On clean exit the persisted scalar, owned-row, and M2M state of each
    tracked root is compared; a meaningful change bumps ``content_revision``
    once and appends an ``edited`` (or ``deleted``) ReviewAction inside the
    same transaction. Ordinary content callbacks may never change protected
    owner/status/revision/approval/submission metadata — such writes roll
    the transaction back.
    """
    model = type(target)
    policy = model_policy(model)
    if policy is None:
        raise PermissionDenied("unsupported_model")
    if getattr(target, "pk", None) is None:
        raise ValidationError("Cannot mutate an unsaved object.")
    moving = proposed_parent is not None
    if moving and (policy.parent_path is None or action != "edit"):
        raise ValidationError("invalid_parent")

    active_roots = _ACTIVE_MUTATION_ROOTS.get() or {}

    with transaction.atomic():
        persisted = model._base_manager.get(pk=target.pk)
        # Generated projections are read-only; the persisted row's marker,
        # not the caller's snapshot, decides.
        if record_policy(persisted).kind == KIND_GENERATED:
            raise PermissionDenied("generated_projection")
        stored_parents = []
        if policy.kind == KIND_OWNED or moving:
            stored_parents = resolve_parents(persisted, policy.parent_path)
            if not stored_parents:
                raise ValidationError("The stored parent could not be resolved.")
        elif policy.parent_path is not None:
            stored_parents = resolve_parents(persisted, policy.parent_path)

        if policy.kind == KIND_OWNED:
            involved = list(stored_parents)
        else:
            involved = [persisted]
        proposed = []
        if moving:
            proposed = (
                [proposed_parent]
                if isinstance(proposed_parent, Model)
                else list(proposed_parent)
            )
            if not proposed or any(
                getattr(candidate, "pk", None) is None for candidate in proposed
            ):
                raise ValidationError("invalid_parent")
            if policy.kind != KIND_OWNED:
                involved.extend(stored_parents)
            involved.extend(
                type(candidate)._base_manager.get(pk=candidate.pk)
                for candidate in proposed
            )

        locked_roots = {}
        for root in sorted(
            {id(r): r for r in involved}.values(),
            key=lambda r: _storage_key(r),
        ):
            key = _storage_key(root)
            if key not in locked_roots:
                locked_roots[key] = _lock_instance(root)

        yield_target = locked_roots.get(_storage_key_for(model, target.pk))
        if policy.kind == KIND_OWNED or not isinstance(yield_target, model):
            yield_target = model._base_manager.select_for_update().get(pk=target.pk)
        if policy.kind == KIND_OWNED or moving:
            stored_keys = {_storage_key(p) for p in stored_parents}
            actual_keys = {
                _storage_key(p)
                for p in resolve_parents(yield_target, policy.parent_path)
            }
            if actual_keys != stored_keys:
                raise PermissionDenied(
                    "The stored parent changed while acquiring locks."
                )

        # Refresh after all potentially blocking locks, including owned rows.
        actor = _fresh_actor(actor)
        if moving:
            locked_proposed = [
                locked_roots[_storage_key(candidate)] for candidate in proposed
            ]
            decision = decide_reassign(actor, yield_target, tuple(locked_proposed))
        else:
            decision = decide(actor, action, yield_target, parent=parent)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)

        if policy.kind == KIND_OWNED:
            primary_key = _storage_key(stored_parents[0])
        else:
            primary_key = _storage_key(yield_target)
        if action == "delete":
            _check_delete_cascade(yield_target, locked_roots[primary_key])

        tracked = {}
        for key, root in locked_roots.items():
            if key in active_roots or not isinstance(root, UserCreatedObject):
                continue
            tracked[key] = (root, _protected_metadata(root), _content_snapshot(root))

        dispositions = {key: {"deleted": False, "deleted_by": None} for key in tracked}
        token = None
        if tracked:
            token = _ACTIVE_MUTATION_ROOTS.set({**active_roots, **dispositions})
        try:
            yield yield_target
        finally:
            if token is not None:
                _ACTIVE_MUTATION_ROOTS.reset(token)

        target_exists = model._base_manager.filter(pk=target.pk).exists()
        # Only a delete aimed at the root itself authorizes its removal; an
        # owned-child delete is an edit of its parent.
        deletes_root = action == "delete" and policy.kind != KIND_OWNED
        if deletes_root and primary_key in active_roots and not target_exists:
            active_roots[primary_key]["deleted"] = True
            active_roots[primary_key]["deleted_by"] = actor
        if policy.parent_path is not None and target_exists:
            # Parent changes are reassignments: without ``proposed_parent``
            # the callback may not attach the row to an unauthorized parent
            # or detach it from all of its stored parents.
            allowed_keys = {_storage_key(p) for p in (*stored_parents, *proposed)}
            current = model._base_manager.get(pk=target.pk)
            current_keys = {
                _storage_key(p) for p in resolve_parents(current, policy.parent_path)
            }
            detached = bool(stored_parents) and not current_keys
            if detached or not current_keys <= allowed_keys:
                raise PermissionDenied(
                    "Changing the parent requires an authorized reassignment."
                )

        for key, (root, protected_before, before) in tracked.items():
            root_action = "delete" if deletes_root and key == primary_key else "edit"
            _finalize_mutation(
                actor,
                root,
                key[1],
                protected_before,
                before,
                root_action,
                dispositions[key],
            )


def record_creation(actor, obj) -> None:
    """Append the ``created`` audit event for a fully initialized root.

    A single creation event is recorded per root and candidate revision;
    nested serializer or helper writes cannot duplicate it. Generated
    projections are skipped: their source owns the meaningful audit trail.
    """
    if not isinstance(obj, UserCreatedObject) or getattr(obj, "pk", None) is None:
        return
    policy = record_policy(obj)
    if policy is None or policy.kind != KIND_REVIEWABLE:
        return
    if (
        _review_actions_for_root(obj)
        .filter(
            action=ReviewAction.ACTION_CREATED,
            content_revision=obj.content_revision,
        )
        .exists()
    ):
        return
    _record_event(
        obj,
        actor,
        ReviewAction.ACTION_CREATED,
        content_revision=obj.content_revision,
        changed_fields=["created"],
    )


def _validate_expected_revision(current, expected, *, required):
    if expected in (None, ""):
        if required:
            raise ValidationError(
                "An inspected content revision is required to approve.",
                code="revision_required",
            )
        return None
    if isinstance(expected, bool):
        raise ValidationError(
            "The supplied content revision is invalid.", code="invalid_revision"
        )
    if not isinstance(expected, int):
        try:
            expected = int(str(expected).strip())
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "The supplied content revision is invalid.",
                code="invalid_revision",
            ) from exc
    if expected < 0:
        raise ValidationError(
            "The supplied content revision is invalid.", code="invalid_revision"
        )
    if expected != current:
        raise StaleRevisionError(expected, current)
    return expected


def _validate_comment_watermark(current, expected):
    if expected in (None, ""):
        return None
    if isinstance(expected, bool):
        raise ValidationError(
            "The supplied content revision is invalid.", code="invalid_revision"
        )
    try:
        watermark = int(str(expected).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "The supplied content revision is invalid.", code="invalid_revision"
        ) from exc
    if watermark < 0 or watermark > current:
        raise ValidationError(
            "The supplied content revision is invalid.", code="invalid_revision"
        )
    return watermark


_CASCADE_EXCEPTIONS = (AttributeError, TypeError, ValidationError, DatabaseError)


def run_review_cascade(obj, action_name, actor, previous_status):
    """Apply the model's ``cascade_review_action`` to linked records.

    Runs in a savepoint inside the transition transaction so an expected
    cascade failure is logged and rolled back without undoing the primary
    transition; unexpected errors propagate and abort the whole transition.
    """
    handler = getattr(obj, "cascade_review_action", None)
    if not callable(handler):
        return
    try:
        with transaction.atomic():
            handler(
                action_name=action_name,
                actor=actor,
                previous_status=previous_status,
            )
    except _CASCADE_EXCEPTIONS as exc:
        logger.warning("Review action cascade failed for %s: %s", obj, exc)


def perform_transition(
    actor,
    target,
    action: str,
    *,
    expected_revision=None,
    comment: str = "",
    cascade: bool = False,
):
    """Apply a named review transition under the root lock.

    ``action`` is one of submit/withdraw/approve/reject/archive. Approval
    requires the caller's inspected ``content_revision`` and excludes the
    owner and every recorded contributor of the current candidate. The
    model's own transition method performs domain validation; the resulting
    audit event is written in the same transaction.
    """
    if action not in _TRANSITION_METHODS:
        raise ValidationError(f"Unsupported transition '{action}'.")
    method_name, review_action = _TRANSITION_METHODS[action]
    record = record_policy(target)
    if record is not None and record.kind == KIND_GENERATED:
        raise PermissionDenied("generated_projection")
    policy = model_policy(type(target))
    if policy is None or policy.kind != KIND_REVIEWABLE:
        raise PermissionDenied("unsupported_model")

    with transaction.atomic():
        fresh = _lock_instance(target)
        fresh._lock_review_dependencies(action)
        actor = _fresh_actor(actor)
        decision = decide(actor, action, fresh)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)
        previous_status = fresh.publication_status
        bound_revision = _validate_expected_revision(
            fresh.content_revision, expected_revision, required=action == "approve"
        )
        if bound_revision is None:
            bound_revision = fresh.content_revision
        transition = getattr(fresh, method_name)
        if action == "approve":
            transition(user=actor)
        else:
            transition()
        if cascade:
            run_review_cascade(fresh, method_name, actor, previous_status)
        if review_action is not None:
            _record_event(
                fresh,
                actor,
                review_action,
                content_revision=bound_revision,
                changed_fields=[],
                comment=comment,
            )
        return fresh


def record_comment(actor, target, comment, *, expected_revision=None):
    """Append a review comment, binding the inspected revision when supplied.

    A supplied watermark must be a valid non-negative revision not newer than
    the current one; older watermarks are retained, absent watermarks stay
    unbound (``content_revision`` null). Comments never bump the revision.
    Comments on a generated projection bind the source evidence thread and
    the source revision — there is no separate projection approval.
    """
    record = record_policy(target)
    if record is not None and record.kind == KIND_GENERATED:
        source = generated_source(target)
        if source is None:
            raise PermissionDenied("invalid_parent")
        target = source
    policy = model_policy(type(target))
    if policy is None or policy.kind != KIND_REVIEWABLE:
        raise PermissionDenied("unsupported_model")
    with transaction.atomic():
        fresh = _lock_instance(target)
        actor = _fresh_actor(actor)
        decision = decide(actor, "comment_on_review", fresh)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)
        watermark = _validate_comment_watermark(
            fresh.content_revision, expected_revision
        )
        return _record_event(
            fresh,
            actor,
            ReviewAction.ACTION_COMMENT,
            content_revision=watermark,
            changed_fields=[],
            comment=comment,
        )


def validate_reassignment(actor, original_target, proposed_parent):
    """Preflight eligibility check for a planned parent reassignment.

    Advisory only — the authoritative decision and lock are established
    inside ``content_mutation(..., proposed_parent=...)`` and held through
    the actual write. An unsaved row, a missing stored parent, or an
    unsaved/empty proposed parent is rejected here.
    """
    if getattr(original_target, "pk", None) is None:
        raise ValidationError("Cannot reassign an unsaved object.")
    policy = model_policy(type(original_target))
    if policy is None or policy.parent_path is None:
        raise ValidationError("invalid_parent")
    if proposed_parent is None:
        raise ValidationError("invalid_parent")
    parents = (
        [proposed_parent]
        if isinstance(proposed_parent, Model)
        else list(proposed_parent)
    )
    if not parents or any(getattr(p, "pk", None) is None for p in parents):
        raise ValidationError("invalid_parent")

    actor = _fresh_actor(actor)
    fresh = type(original_target)._base_manager.get(pk=original_target.pk)
    decision = decide_reassign(actor, fresh, proposed_parent)
    if not decision.allowed:
        raise PermissionDenied(decision.reason)
    return True


def is_independent_evidence_model(model) -> bool:
    policy = model_policy(model)
    return (
        policy is not None
        and policy.kind == KIND_REVIEWABLE
        and policy.parent_path is not None
    )


def save_evidence_formset_rows(actor, formset, parent) -> None:
    """Persist an independent-evidence workspace formset row by row.

    Each changed row is its own registry root: edits/deletes run inside a
    ``content_mutation`` on the evidence record itself and creations are
    recorded with ``record_creation`` — never as edits of the parent. The
    caller is expected to hold an outer ``transaction.atomic`` batch and to
    have validated the formset already.
    """
    actor = _fresh_actor(actor)
    for form in formset.forms:
        data = getattr(form, "cleaned_data", None)
        if not data:
            continue
        row = data.get("id")
        if data.get("DELETE"):
            if row is not None:
                with content_mutation(actor, row, action="delete") as locked_row:
                    locked_row.delete()
            continue
        if row is None:
            if not form.has_changed():
                continue
            instance = form.save(commit=False)
            fk = getattr(formset, "fk", None)
            if fk is not None and getattr(formset, "instance", None) is not None:
                setattr(instance, fk.name, formset.instance)
            create_parent = (
                resolve_create_parent(model_policy(type(instance)), instance, data)
                or parent
            )
            decision = decide(actor, "create", type(instance), parent=create_parent)
            if not decision.allowed:
                raise PermissionDenied(decision.reason)
            if isinstance(instance, UserCreatedObject):
                instance.owner = actor
                instance.publication_status = UserCreatedObject.STATUS_PRIVATE
            instance.save()
            if hasattr(form, "save_m2m"):
                form.save_m2m()
            record_creation(actor, instance)
            continue
        if not form.has_changed():
            continue
        proposed = None
        policy = model_policy(type(row))
        if policy is not None and policy.parent_path is not None:
            parent_field = policy.parent_path.split("__")[0]
            if parent_field in getattr(form, "changed_data", []):
                proposed = data.get(parent_field)
        with content_mutation(
            actor, row, action="edit", proposed_parent=proposed
        ) as locked_row:
            form.instance = locked_row
            # Re-run validation against the locked row so clean_* side
            # effects apply to the object that is actually saved.
            form.full_clean()
            if form.errors:
                raise ValidationError(list(form.errors.values()))
            construct_instance(form, locked_row)
            form.save()
            if hasattr(form, "save_m2m"):
                form.save_m2m()


_URL_CHECK_JOB_PREFIX = "url-check-job:"
_URL_CHECK_JOB_TTL = 24 * 3600


def register_url_check_job(task_id, user, target=None):
    """Bind a URL-health task id to the initiating actor and target."""
    from django.core.cache import cache

    payload = {"user_id": getattr(user, "pk", None)}
    if target is not None:
        payload["target"] = f"{target._meta.label_lower}:{target.pk}"
    cache.set(f"{_URL_CHECK_JOB_PREFIX}{task_id}", payload, timeout=_URL_CHECK_JOB_TTL)


def authorize_url_check_job(user, task_id):
    """Return the bound target for a job that belongs to *user*.

    Raises ``Http404`` for unknown or foreign job ids so progress polling
    cannot disclose other users' task data. When the job was bound to a
    target row, current read access is re-evaluated and a revoked grant
    denies with ``PermissionDenied``.
    """
    from django.core.cache import cache
    from django.http import Http404

    job = cache.get(f"{_URL_CHECK_JOB_PREFIX}{task_id}")
    if not isinstance(job, dict) or job.get("user_id") != getattr(user, "pk", None):
        raise Http404("Unknown URL check job.")
    label = job.get("target")
    if not label:
        return None
    model_label, _, pk = label.rpartition(":")
    model = apps.get_model(model_label)
    target = model.objects.filter(pk=pk).first() if model else None
    if target is None or not decide(user, "read", target).allowed:
        raise PermissionDenied("URL check target is no longer accessible.")
    return target


_ACCESS_CHANGE_ACTIONS = frozenset(
    {
        "add_editor",
        "remove_editor",
        "add_editor_group",
        "remove_editor_group",
        "transfer_ownership",
    }
)


def perform_access_change(actor, target, action, recipient):
    """Apply one sharing mutation on ``target`` inside a locked boundary.

    Accepted ``action`` strings are exactly ``add_editor``, ``remove_editor``,
    ``add_editor_group``, ``remove_editor_group``, and ``transfer_ownership``;
    anything else is a ``ValidationError`` before any write. Only reviewable
    roots participate — owned children and generated projections cannot gain
    independently governed grants. The actor is re-read after the row lock is
    acquired and the canonical ``transfer_ownership``/``manage_editors``
    decision is authoritative; advisory view checks are not. The recipient is
    freshly reloaded and must be a persisted row of the type the action
    requires (``User`` for editor/transfer actions, ``Group`` for group
    actions). The model-level helpers on the locked object then perform the
    write with the fresh actor recorded as grantor/initiator; the freshly
    locked target is returned.
    """
    if action not in _ACCESS_CHANGE_ACTIONS:
        raise ValidationError(f"Unknown access action: {action!r}.")
    policy = record_policy(target)
    if policy is None or policy.kind != KIND_REVIEWABLE:
        raise ValidationError(
            "Sharing applies only to independently reviewable records."
        )
    group_action = action in ("add_editor_group", "remove_editor_group")
    expected_model = Group if group_action else get_user_model()
    if (
        not isinstance(recipient, expected_model)
        or getattr(recipient, "pk", None) is None
    ):
        raise ValidationError("Invalid recipient for this access action.")

    with transaction.atomic():
        locked = _lock_instance(target)
        locked_policy = record_policy(locked)
        if locked_policy is None or locked_policy.kind != KIND_REVIEWABLE:
            raise ValidationError(
                "Sharing applies only to independently reviewable records."
            )
        fresh_actor = _fresh_actor(actor)
        decision_action = (
            "transfer_ownership" if action == "transfer_ownership" else "manage_editors"
        )
        if not decide(fresh_actor, decision_action, locked).allowed:
            raise PermissionDenied("You don't have permission to change sharing.")
        fresh_recipient = expected_model._base_manager.filter(pk=recipient.pk).first()
        if fresh_recipient is None:
            raise ValidationError("The selected recipient no longer exists.")
        if group_action:
            if action == "add_editor_group":
                locked.add_editor_group(fresh_recipient, granted_by=fresh_actor)
            else:
                locked.remove_editor_group(fresh_recipient)
        elif action == "add_editor":
            locked.add_editor(fresh_recipient, granted_by=fresh_actor)
        elif action == "remove_editor":
            locked.remove_editor(fresh_recipient)
        else:
            locked.transfer_ownership(fresh_recipient, initiator=fresh_actor)
        return locked
