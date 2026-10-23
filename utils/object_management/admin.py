"""Policy-aware Django admin adapters.

``PolicyAdminMixin`` maps the admin verbs onto the shared object-management
core: changelist rows come from ``visible_queryset``, per-object
view/change/delete delegate to ``decide``, adds use the model-level ``create``
decision, and changeform POSTs run inside one ``content_mutation`` boundary so
model, inline, and M2M writes share a single locked root revision.

Parent relations declared in the registry are structural: once persisted they
are read-only in the admin and reassignment must go through the specialized
policy path (``content_mutation`` with ``proposed_parent``). Forged POSTed
parent values are rejected instead of silently ignored.

``PolicyOwnedInlineMixin`` applies the same rules to owned-child inlines
(KIND_OWNED only): their add/change/delete capability is the parent root's
edit decision, so no separate owned-child grant is required and frozen
parents cannot be edited. Registered independent-evidence or other non-owned
models fail closed on this adapter.

Admins and inlines marked ``policy_administrator_only`` additionally require
explicit application administration for every write verb and at persistence
time; read/list still follow core visibility, and a frozen parent denies even
administrators.

``ReviewActionAdmin`` is append-only: review events are never added, changed,
or deleted through the admin, and the listing is restricted to targets for
which the acting user holds ``view_review_activity``.
"""

import sys
from contextlib import ExitStack
from functools import reduce
from operator import or_

from django.apps import apps
from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models import Model, ProtectedError, Q, RestrictedError
from django.forms.models import construct_instance
from django.template.response import TemplateResponse

from .models import ReviewAction, UserCreatedObject
from .policy import (
    decide,
    editable_queryset,
    is_active_actor,
    is_admin,
    is_moderator,
    scope_queryset,
    visible_queryset,
)
from .registry import (
    KIND_OWNED,
    KIND_REVIEWABLE,
    REVIEWABLE_MODELS,
    administrator_managed,
    model_policy,
    resolve_create_parent,
    root_model,
)
from .services import (
    _fresh_actor,
    authorize_create,
    content_mutation,
    record_creation,
    validate_created_parent,
    validate_references,
)

_METADATA_READONLY_FIELDS = (
    "owner",
    "publication_status",
    "content_revision",
    "created_by",
    "created_at",
    "lastmodified_by",
    "lastmodified_at",
    "submitted_at",
    "submitted_by",
    "approved_at",
    "approved_by",
    # Server-controlled generated-projection linkage (CPV only).
    "is_derived",
    "derived_from",
)

_ADMIN_ACTION_MAP = {"view": "read", "change": "edit", "delete": "delete"}

_POLICY_BOUNDARIES_ATTR = "_policy_boundaries"

_OWNED_SAVE_BOUNDARIES_ATTR = "_policy_owned_save_boundaries"
_PENDING_PARENT_CHECKS_ATTR = "_policy_pending_parent_checks"


def _model_has_field(model, name):
    try:
        model._meta.get_field(name)
    except FieldDoesNotExist:
        return False
    return True


def _policy_boundary_key(obj):
    return (obj._meta.label_lower, obj.pk)


def _scope_relation_formfield(formfield, db_field, user):
    """Narrow a registered related-model formfield to visible rows; an
    unregistered UCO relation offers nothing (fail closed)."""
    related = getattr(db_field.remote_field, "model", None)
    if formfield is None or getattr(formfield, "queryset", None) is None:
        return formfield
    if related is not None and (
        model_policy(related) is not None or issubclass(related, UserCreatedObject)
    ):
        formfield.queryset = visible_queryset(user, formfield.queryset)
    return formfield


def _metadata_readonly(model, fields, readonly):
    for field_name in fields:
        if _model_has_field(model, field_name) and field_name not in readonly:
            readonly.append(field_name)
    return readonly


def _normalized_parents(parent):
    """Return the resolved create-parent(s) as a model instance or list."""
    if parent is None or isinstance(parent, Model):
        return parent
    if isinstance(parent, (list, tuple)):
        return list(parent)
    # ModelMultipleChoiceField cleaned values arrive as a QuerySet.
    return list(parent)


def _formset_touched(formset):
    """Whether a bound inline formset contains any row change."""
    return bool(getattr(formset, "deleted_forms", [])) or any(
        getattr(form_item, "has_changed", lambda: False)()
        for form_item in formset.forms
    )


def _active_admin_actor(request, admin_site):
    """Re-read the request actor and re-check site eligibility at the
    persistence hook — a revoked staff flag or deactivated account must
    deny, and ``request.user`` is refreshed so downstream decisions see
    the live record."""
    actor = _fresh_actor(request.user)
    request.user = actor
    if not admin_site.has_permission(request):
        raise PermissionDenied("staff_required")
    return actor


class PolicyAdminMixin:
    """Django admin adapter delegating object verbs to the policy core."""

    # Server-managed metadata is never editable through the admin form.
    policy_metadata_readonly = _METADATA_READONLY_FIELDS
    # Specialized adapters (e.g. dataset runtime configuration) may require
    # explicit application administration for writes in addition to the core
    # decision. Read/list still follow core visibility.
    policy_administrator_only = False

    def get_policy_model(self):
        return self.model

    def _model_policy(self):
        model = self.get_policy_model()
        return model, model_policy(model) if model is not None else None

    def _is_unregistered_uco(self):
        model, policy = self._model_policy()
        return (
            model is not None
            and policy is None
            and issubclass(model, UserCreatedObject)
        )

    def _admin_write_denied(self, request):
        return self.policy_administrator_only and not is_admin(request.user)

    def _authorize_write(self, request, action, obj=None, *, parent=None):
        """Fresh actor + administrator narrowing + core decision at the
        persistence hook. ``create`` runs through ``authorize_create`` so the
        fresh actor and live parent are used, never cached form data."""
        actor = _active_admin_actor(request, self.admin_site)
        if self._admin_write_denied(request):
            raise PermissionDenied("administrator_required")
        if action == "create":
            actor = authorize_create(
                actor,
                self.get_policy_model(),
                parent=parent,
            )
            request.user = actor
            if not self.admin_site.has_permission(request):
                raise PermissionDenied("staff_required")
            if self._admin_write_denied(request):
                raise PermissionDenied("administrator_required")
            return actor
        persisted = type(obj)._base_manager.get(pk=obj.pk)
        decision = decide(actor, _ADMIN_ACTION_MAP[action], persisted, parent=parent)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)
        return actor

    def _policy_metadata_readonly(self, model, readonly):
        return _metadata_readonly(model, self.policy_metadata_readonly, readonly)

    def _has_editable_parent(self, request, model, policy):
        """Standalone owned-child adds are offered when the actor may edit at
        least one root of the declared parent type; the concrete parent is
        still authorized per request at save time."""
        if not is_active_actor(request.user):
            return False
        root = root_model(model, policy.parent_path)
        if root is None:
            return False
        return editable_queryset(request.user, root._base_manager.all()).exists()

    def _policy_allows(self, request, admin_action, obj=None):
        """Return the core decision for the verb, or None when not governed."""
        model, policy = self._model_policy()
        if model is None:
            return None
        if policy is None:
            if self._is_unregistered_uco() and admin_action in (
                "add",
                "change",
                "delete",
            ):
                return False
            return None
        # Administrator-only adapters narrow every write verb, including
        # the class-level fallbacks; read/list follow core visibility.
        if admin_action in ("add", "change", "delete") and self._admin_write_denied(
            request
        ):
            return False
        if admin_action == "add":
            if policy.kind == KIND_OWNED:
                return self._has_editable_parent(request, model, policy)
            return decide(request.user, "create", model).allowed
        if obj is None:
            # List-level capability: rows/actions are scoped by
            # get_queryset and per-object checks.
            return decide(request.user, "list", model).allowed
        return decide(request.user, _ADMIN_ACTION_MAP[admin_action], obj).allowed

    def has_view_permission(self, request, obj=None):
        allowed = self._policy_allows(request, "view", obj)
        if allowed is not None:
            return allowed
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        allowed = self._policy_allows(request, "change", obj)
        if allowed is not None:
            return allowed
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        allowed = self._policy_allows(request, "add")
        if allowed is not None:
            return allowed
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        allowed = self._policy_allows(request, "delete", obj)
        if allowed is not None:
            return allowed
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        model, policy = self._model_policy()
        if policy is not None:
            return visible_queryset(request.user, queryset)
        if self._is_unregistered_uco():
            return queryset.none()
        return queryset

    def get_actions(self, request):
        actions = super().get_actions(request)
        _, policy = self._model_policy()
        if policy is not None and "delete_selected" in actions:
            # The stock template hard-codes ``action=delete_selected`` — keep
            # the standard identifier so no template fork is needed.
            actions["delete_selected"] = (
                PolicyAdminMixin.policy_delete_selected,
                "delete_selected",
                "Delete selected records",
            )
        return actions

    def get_deleted_objects(self, objs, request):
        """Core cascade/permission precheck before Django formats related
        names — a blocked delete raises PermissionDenied so no hidden leaf
        reaches the preview."""
        model, policy = self._model_policy()
        if policy is not None:
            for obj in objs:
                try:
                    with content_mutation(request.user, obj, action="delete") as locked:
                        self._authorize_write(request, "delete", locked)
                except (ProtectedError, RestrictedError, model.DoesNotExist):
                    raise PermissionDenied("deletion_not_permitted") from None
        return super().get_deleted_objects(objs, request)

    def _policy_delete_one(self, request, obj, *, log_deletion=True):
        """Delete one governed root inside its own boundary; the audit log
        entry is written while the row still carries its primary key."""
        with content_mutation(request.user, obj, action="delete") as locked:
            self._authorize_write(request, "delete", locked)
            if log_deletion:
                self.log_deletions(request, [locked])
            locked.delete()

    def policy_delete_selected(self, request, queryset):
        """Confirmation-gated bulk delete under the standard action id.

        The first pass only previews via ``get_deleted_objects`` (which ran
        the core cascade precheck). The confirmed ``post=yes`` pass re-checks
        and deletes each allowed root inside its own boundary, logging real
        deletions only — never the stock all-N success count."""
        if request.method != "POST":
            raise PermissionDenied("post_required")
        _active_admin_actor(request, self.admin_site)
        if self._admin_write_denied(request):
            raise PermissionDenied("administrator_required")
        queryset = visible_queryset(request.user, queryset)

        def _deletable(obj):
            try:
                with content_mutation(request.user, obj, action="delete"):
                    return True
            except (PermissionDenied, ProtectedError, RestrictedError):
                return False
            except queryset.model.DoesNotExist:
                return False

        if request.POST.get("post") != "yes":
            eligible = [obj for obj in queryset if _deletable(obj)]
            blocked = queryset.count() - len(eligible)
            if not eligible:
                self.message_user(
                    request, "No permitted records selected.", level=messages.WARNING
                )
                return None
            (
                deletable_objects,
                model_count,
                perms_lacking,
                protected,
            ) = self.get_deleted_objects(eligible, request)
            opts = self.model._meta
            context = dict(
                self.admin_site.each_context(request),
                opts=opts,
                title="Delete multiple objects",
                objects_name=str(opts.verbose_name_plural),
                queryset=eligible,
                deletable_objects=[deletable_objects],
                model_count=dict(model_count).items(),
                perms_lacking=perms_lacking,
                protected=protected,
                blocked_count=blocked,
                action_checkbox_name=admin.helpers.ACTION_CHECKBOX_NAME,
                media=self.media,
            )
            if blocked:
                self.message_user(
                    request,
                    f"{blocked} record(s) skipped: deletion not permitted.",
                    level=messages.WARNING,
                )
            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                "admin/delete_selected_confirmation.html",
                context,
            )

        self.delete_queryset(request, queryset)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        model, policy = self._model_policy()
        if policy is not None:
            readonly = self._policy_metadata_readonly(model, readonly)
            # Persisted registry parent relations are structural and stay
            # read-only; reassignment goes through the specialized policy path.
            if obj is not None and obj.pk is not None and policy.parent_path:
                parent_field = policy.parent_path.split("__")[0]
                if (
                    _model_has_field(model, parent_field)
                    and parent_field not in readonly
                ):
                    readonly.append(parent_field)
        return readonly

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return _scope_relation_formfield(formfield, db_field, request.user)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        return _scope_relation_formfield(formfield, db_field, request.user)

    # The changeform boundary is opened in ``changeform_view``; request-local
    # state keyed to the locked object keeps ``save_model`` safe for direct
    # callers outside it and never leaks across requests.
    def _open_policy_boundary(self, request, obj):
        boundaries = getattr(request, _POLICY_BOUNDARIES_ATTR, None)
        if boundaries is None:
            boundaries = {}
            setattr(request, _POLICY_BOUNDARIES_ATTR, boundaries)
        boundaries[_policy_boundary_key(obj)] = True

    def _policy_boundary_open(self, request, obj):
        boundaries = getattr(request, _POLICY_BOUNDARIES_ATTR, None) or {}
        return _policy_boundary_key(obj) in boundaries

    def _close_policy_boundary(self, request, obj):
        boundaries = getattr(request, _POLICY_BOUNDARIES_ATTR, None)
        if boundaries is not None:
            boundaries.pop(_policy_boundary_key(obj), None)

    # Owned-save boundaries opened in ``save_model`` live on the request in
    # an ExitStack keyed to the locked parent: a repeated registration for
    # the same root reuses the open boundary, and unwinding is LIFO — an
    # exit failure can never prevent the remaining boundaries (and their
    # _ACTIVE_MUTATION_ROOTS ContextVar state) from unwinding.
    def _open_owned_save_boundary(self, request, parent):
        state = getattr(request, _OWNED_SAVE_BOUNDARIES_ATTR, None)
        if state is None:
            state = {"stack": ExitStack(), "by_parent": {}}
            setattr(request, _OWNED_SAVE_BOUNDARIES_ATTR, state)
        key = _policy_boundary_key(parent)
        if key not in state["by_parent"]:
            state["by_parent"][key] = state["stack"].enter_context(
                content_mutation(request.user, parent, action="edit")
            )
        return state["by_parent"][key]

    def _close_owned_save_boundaries(self, request, exc_type=None, exc=None, tb=None):
        state = getattr(request, _OWNED_SAVE_BOUNDARIES_ATTR, None)
        if state is None:
            return
        setattr(request, _OWNED_SAVE_BOUNDARIES_ATTR, None)
        state["stack"].__exit__(exc_type, exc, tb)

    def add_view(self, request, form_url="", extra_context=None):
        # Root + M2M + inline writes of one POST must commit atomically: a
        # persistence-time denial must not leave the freshly created root
        # or its creation audit behind. Boundary teardown happens while the
        # atomic block is still open so savepoints unwind in order.
        _, policy = self._model_policy()
        if request.method == "POST" and policy is not None:
            with transaction.atomic():
                request.user = _fresh_actor(request.user)
                try:
                    return super().add_view(request, form_url, extra_context)
                finally:
                    setattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
                    self._close_owned_save_boundaries(request, *sys.exc_info())
        return super().add_view(request, form_url, extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        model, policy = self._model_policy()
        if request.method == "POST" and object_id is not None and policy is not None:
            obj = self.get_object(request, object_id)
            if obj is None:
                return super().changeform_view(
                    request, object_id, form_url, extra_context
                )
            with content_mutation(request.user, obj, action="edit") as locked:
                # The request actor is re-read only after the root lock is
                # held; staff admission is site eligibility, not authority —
                # a revoked flag must not complete a waiting POST.
                request.user = _fresh_actor(request.user)
                if not self.admin_site.has_permission(request):
                    raise PermissionDenied("staff_required")
                self._open_policy_boundary(request, locked)
                try:
                    return super().changeform_view(
                        request, str(locked.pk), form_url, extra_context
                    )
                finally:
                    setattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
                    self._close_policy_boundary(request, locked)
                    self._close_owned_save_boundaries(request, *sys.exc_info())
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _reject_forged_parent_change(self, request, obj, policy):
        """Persisted parent relations are read-only in the admin: a posted
        parent value that differs from the stored relation is a forged
        reparent attempt and must fail instead of being silently ignored."""
        if not policy.parent_path:
            return
        field_name = policy.parent_path.split("__")[0]
        try:
            field = obj._meta.get_field(field_name)
        except Exception:
            return
        if field_name not in request.POST:
            return
        posted = sorted(value for value in request.POST.getlist(field_name) if value)
        # ``obj`` is the form-populated instance already carrying the posted
        # values; compare against the persisted relation instead.
        persisted = type(obj)._base_manager.get(pk=obj.pk)
        if getattr(field, "many_to_many", False):
            stored = sorted(
                str(pk)
                for pk in getattr(persisted, field_name).values_list("pk", flat=True)
            )
            forged = posted != stored
        else:
            stored = getattr(persisted, f"{field_name}_id", None)
            forged = len(posted) != 1 or posted[0] != str(stored or "")
        if forged:
            raise PermissionDenied("invalid_parent")

    def _validated_create_parent(self, policy, obj, form):
        """Resolve the declared create parent(s) from validated form data."""
        if not policy.parent_path:
            return None
        parent = resolve_create_parent(
            policy,
            instance=obj,
            validated_data=getattr(form, "cleaned_data", None),
        )
        return _normalized_parents(parent)

    def _assign_server_metadata(self, request, obj):
        policy = model_policy(type(obj))
        if not isinstance(obj, UserCreatedObject) and (
            policy is None or policy.kind != KIND_OWNED
        ):
            return
        if _model_has_field(type(obj), "owner"):
            obj.owner = request.user
        if _model_has_field(type(obj), "publication_status"):
            obj.publication_status = UserCreatedObject.STATUS_PRIVATE

    def _save_owned(self, request, obj, form, change):
        """Persist an owned child under the parent root's edit boundary.

        Creates authorize ``decide(create, child, parent=cleaned_parent)`` and
        run inside the parent's ``content_mutation``, which stays open through
        ``save_related`` so one meaningful write yields one parent revision.
        """
        if change:
            if self._policy_boundary_open(request, obj):
                actor = self._authorize_write(request, "change", obj)
                validate_references(actor, getattr(form, "cleaned_data", {}))
                construct_instance(form, obj)
                return super().save_model(request, obj, form, change)
            with content_mutation(request.user, obj, action="edit") as locked:
                actor = self._authorize_write(request, "change", locked)
                validate_references(actor, getattr(form, "cleaned_data", {}))
                construct_instance(form, locked)
                form.instance = locked
                super().save_model(request, locked, form, change)
            return

        parent = self._validated_create_parent(model_policy(type(obj)), obj, form)
        if (
            parent is None
            or not isinstance(parent, Model)
            or getattr(parent, "pk", None) is None
        ):
            raise PermissionDenied("invalid_parent")
        locked_parent = self._open_owned_save_boundary(request, parent)
        try:
            actor = self._authorize_write(request, "create", obj, parent=locked_parent)
            validate_references(actor, getattr(form, "cleaned_data", {}))
            self._assign_server_metadata(request, obj)
            super().save_model(request, obj, form, change)
            validate_created_parent(obj, parent=locked_parent)
        except BaseException:
            self._close_owned_save_boundaries(request, *sys.exc_info())
            raise

    def save_model(self, request, obj, form, change):
        model, policy = self._model_policy()
        if policy is None:
            if self._is_unregistered_uco():
                raise PermissionDenied("unsupported_model")
            return super().save_model(request, obj, form, change)
        if change:
            self._reject_forged_parent_change(request, obj, policy)
        if policy.kind == KIND_OWNED:
            self._save_owned(request, obj, form, change)
            return
        if not change:
            # Independent evidence and standalone roots validate their
            # declared parent(s) from cleaned data; create authorization
            # uses the fresh actor and live parent via authorize_create.
            parent = self._validated_create_parent(policy, obj, form)
            if policy.parent_path and (
                parent is None or (isinstance(parent, list) and not parent)
            ):
                raise PermissionDenied("invalid_parent")
            actor = self._authorize_write(request, "create", parent=parent)
            validate_references(actor, getattr(form, "cleaned_data", {}))
            self._assign_server_metadata(request, obj)
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                if parent is not None:
                    # Many-valued parents (e.g. M2M ``collections``) are only
                    # written in ``save_related`` — defer the persisted-parent
                    # check so the whole compound write stays atomic.
                    pending = getattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
                    if pending is None:
                        pending = []
                        setattr(request, _PENDING_PARENT_CHECKS_ATTR, pending)
                    pending.append((obj, parent))
                record_creation(actor, obj)
            return
        if self._policy_boundary_open(request, obj):
            actor = self._authorize_write(request, "change", obj)
            validate_references(actor, getattr(form, "cleaned_data", {}))
            construct_instance(form, obj)
            return super().save_model(request, obj, form, change)
        with content_mutation(request.user, obj, action="edit") as locked:
            actor = self._authorize_write(request, "change", locked)
            validate_references(actor, getattr(form, "cleaned_data", {}))
            construct_instance(form, locked)
            form.instance = locked
            super().save_model(request, locked, form, change)

    def save_formset(self, request, form, formset, change):
        # ``save_formset`` is invoked on the *parent* ModelAdmin, not the
        # inline — reauthorize governed inline writes here before the
        # native formset save. The permission predicates only steer
        # rendering, so a forged management form cannot smuggle extra,
        # changed, or deleted rows past the parent's gate. Any governed
        # inline model whose declared adapter lacks ``authorize_formset``
        # — including an owned-only adapter misused on independent
        # evidence — fails closed on touched rows, as does a governed
        # formset model with no matching declared inline at all.
        if model_policy(formset.model) is not None:
            inline = None
            for inline_class in self.get_inlines(request, formset.instance):
                if inline_class.model is formset.model:
                    inline = inline_class(self.model, self.admin_site)
                    break
            authorize = getattr(inline, "authorize_formset", None)
            if authorize is not None:
                authorize(request, formset, change)
                for child_form in formset.forms:
                    if (
                        child_form.instance.pk is None
                        and child_form.has_changed()
                        and not child_form.cleaned_data.get("DELETE", False)
                    ):
                        self._assign_server_metadata(request, child_form.instance)
            elif _formset_touched(formset):
                raise PermissionDenied("unsupported_model")
        return super().save_formset(request, form, formset, change)

    def save_related(self, request, form, formsets, change):
        model, policy = self._model_policy()
        try:
            if policy is not None:
                if change:
                    actor = self._authorize_write(request, "change", form.instance)
                else:
                    parent = self._validated_create_parent(policy, form.instance, form)
                    actor = self._authorize_write(
                        request, "create", form.instance, parent=parent
                    )
                validate_references(actor, getattr(form, "cleaned_data", {}))
            super().save_related(request, form, formsets, change)
            pending = getattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
            setattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
            for saved_obj, expected in pending or ():
                validate_created_parent(saved_obj, parent=expected)
        except BaseException:
            setattr(request, _PENDING_PARENT_CHECKS_ATTR, None)
            self._close_owned_save_boundaries(request, *sys.exc_info())
            raise
        self._close_owned_save_boundaries(request)

    def delete_model(self, request, obj):
        model, policy = self._model_policy()
        if policy is not None:
            _active_admin_actor(request, self.admin_site)
            if self._admin_write_denied(request):
                raise PermissionDenied("administrator_required")
            # Django's delete view already logged this row in its transaction.
            self._policy_delete_one(request, obj, log_deletion=False)
            return
        if self._is_unregistered_uco():
            raise PermissionDenied("unsupported_model")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        model, policy = self._model_policy()
        if policy is None:
            if self._is_unregistered_uco():
                raise PermissionDenied("unsupported_model")
            return super().delete_queryset(request, queryset)
        _active_admin_actor(request, self.admin_site)
        if self._admin_write_denied(request):
            raise PermissionDenied("administrator_required")
        denied = 0
        deleted = 0
        for obj in queryset:
            try:
                self._policy_delete_one(request, obj)
            except (PermissionDenied, ProtectedError, RestrictedError):
                denied += 1
            except queryset.model.DoesNotExist:
                denied += 1
            else:
                deleted += 1
        if denied:
            self.message_user(
                request,
                f"{denied} record(s) skipped: deletion not permitted.",
                level=messages.WARNING,
            )
        if deleted:
            self.message_user(
                request, f"Deleted {deleted} record(s).", level=messages.SUCCESS
            )


class PolicyOwnedInlineMixin:
    """Inline adapter for registry-owned children only (``KIND_OWNED``).

    On a persisted parent, add/change/delete delegate to the parent root's
    edit decision; on an unsaved parent (compound creation, e.g. Source with
    author rows) they delegate to the parent's create decision. Registered
    non-owned models must not use this adapter — it fails closed on them.
    """

    policy_administrator_only = False
    policy_metadata_readonly = _METADATA_READONLY_FIELDS

    def _inline_model_policy(self):
        model = getattr(self, "model", None)
        return model, model_policy(model) if model is not None else None

    def _inline_write_denied(self, request):
        return (
            self.policy_administrator_only or administrator_managed(self.model)
        ) and not is_admin(request.user)

    def _declared_parent_field(self):
        model, policy = self._inline_model_policy()
        if policy is None or policy.kind != KIND_OWNED or not policy.parent_path:
            return None
        first_hop = policy.parent_path.split("__")[0]
        try:
            field = model._meta.get_field(first_hop)
        except FieldDoesNotExist:
            return None
        related = getattr(field, "related_model", None)
        if (
            related is None
            or field.many_to_many
            or not issubclass(self.parent_model, related)
            or (self.fk_name is not None and self.fk_name != first_hop)
        ):
            return None
        return field

    def _parent_context(self, obj):
        field = self._declared_parent_field()
        if field is None or not isinstance(obj, field.related_model):
            return None
        return resolve_create_parent(
            model_policy(self.model), validated_data={field.name: obj}
        )

    def _parent_gate(self, request, obj, action):
        if self._inline_write_denied(request):
            return False
        if self._declared_parent_field() is None:
            return False
        if obj is None or getattr(obj, "pk", None) is None:
            if action == "add":
                return decide(request.user, "create", self.parent_model).allowed
            return editable_queryset(
                request.user, self.parent_model._base_manager.all()
            ).exists()
        parent = self._parent_context(obj)
        return (
            parent is not None
            and decide(request.user, "create", self.model, parent=parent).allowed
        )

    def has_view_permission(self, request, obj=None):
        # Read follows the parent: parent-readable rows show their owned
        # children even to actors without child-model permissions.
        field = self._declared_parent_field()
        if field is None:
            return False
        if obj is not None and not isinstance(obj, field.related_model):
            return False
        if obj is None or getattr(obj, "pk", None) is None:
            return visible_queryset(
                request.user, self.parent_model._base_manager.all()
            ).exists()
        return decide(request.user, "read", obj).allowed

    def get_queryset(self, request):
        # Owned children surface only where their declared parent is
        # readable by the acting user.
        queryset = super().get_queryset(request)
        if self._declared_parent_field() is None:
            return queryset.none()
        return visible_queryset(request.user, queryset)

    def has_add_permission(self, request, obj=None):
        model, policy = self._inline_model_policy()
        if policy is None or policy.kind != KIND_OWNED:
            return False
        return self._parent_gate(request, obj, "add")

    def has_change_permission(self, request, obj=None):
        model, policy = self._inline_model_policy()
        if policy is None or policy.kind != KIND_OWNED:
            return False
        return self._parent_gate(request, obj, "change")

    def has_delete_permission(self, request, obj=None):
        model, policy = self._inline_model_policy()
        if policy is None or policy.kind != KIND_OWNED:
            return False
        return self._parent_gate(request, obj, "delete")

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        model, policy = self._inline_model_policy()
        if policy is not None and model is not None:
            readonly = _metadata_readonly(
                model, self.policy_metadata_readonly, readonly
            )
        return readonly

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return _scope_relation_formfield(formfield, db_field, request.user)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        return _scope_relation_formfield(formfield, db_field, request.user)

    def authorize_formset(self, request, formset, change):
        """Reauthorize touched inline rows at persistence time.

        Invoked by ``PolicyAdminMixin.save_formset`` on the *parent* admin —
        ``InlineModelAdmin`` has no ``save_formset`` hook of its own. A
        forged extra, changed, or deleted row cannot bypass the permission
        predicates, which Django only consults for rendering and
        initial-form handling. Non-owned inline models fail closed.
        """
        model, policy = self._inline_model_policy()
        if policy is None or policy.kind != KIND_OWNED:
            if _formset_touched(formset):
                raise PermissionDenied("unsupported_model")
            return
        # Declared binding: the formset's actual FK is the first hop of the
        # owned parent_path, and that hop resolves to this inline's declared
        # parent model — a misbound inline (SourceAuthor via ``author``)
        # fails closed at persistence.
        field = self._declared_parent_field()
        fk = getattr(formset, "fk", None)
        if field is None or fk is None or fk.name != field.name:
            raise PermissionDenied("invalid_parent")
        # Every supplied existing-child id — including delete-marked rows —
        # must belong to this parent; compare the persisted FK, never the
        # POST-mutated ``form.instance``.
        posted_pks = set()
        for bound_form in formset.forms:
            pk_value = bound_form.data.get(
                bound_form.add_prefix(formset.model._meta.pk.name)
            ) or bound_form.data.get(bound_form.add_prefix("id"))
            if pk_value:
                posted_pks.add(pk_value)
        if posted_pks:
            persisted_rows = {
                str(row.pk): getattr(row, fk.attname)
                for row in formset.model._base_manager.filter(pk__in=posted_pks)
            }
            for pk_value in posted_pks:
                if persisted_rows.get(pk_value) != formset.instance.pk:
                    raise PermissionDenied("invalid_parent")
        if not _formset_touched(formset):
            return
        actor = _active_admin_actor(request, self.admin_site)
        if change:
            parent = self._parent_context(formset.instance)
            actor = authorize_create(actor, self.model, parent=parent)
        else:
            parent_policy = model_policy(self.parent_model)
            parent = resolve_create_parent(parent_policy, instance=formset.instance)
            actor = authorize_create(actor, self.parent_model, parent=parent)
        request.user = actor
        if not self.admin_site.has_permission(request):
            raise PermissionDenied("staff_required")
        if self._inline_write_denied(request):
            raise PermissionDenied("administrator_required")
        # References are re-validated only on touched, non-deleted rows —
        # deleting must not require reading a now-inaccessible reference.
        for bound_form in formset.forms:
            if (
                bound_form not in getattr(formset, "deleted_forms", ())
                and getattr(bound_form, "cleaned_data", None)
                and getattr(bound_form, "has_changed", lambda: False)()
            ):
                validate_references(actor, bound_form.cleaned_data)


@admin.register(ReviewAction)
class NamedUserCreatedObjectAdmin(admin.ModelAdmin):
    """Shared admin configuration for NamedUserCreatedObject subclasses."""

    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


class ReviewActionAdmin(admin.ModelAdmin):
    """Read-only audit log: review events are append-only, even for superusers.

    The changelist is restricted to events bound to targets for which the
    acting user holds ``view_review_activity``. Administrators retain the
    full history, including events whose target was deleted.
    """

    list_display = (
        "__str__",
        "action",
        "user",
        "content_type",
        "object_id",
        "created_at",
    )
    search_fields = ("comment", "user__username")
    list_filter = ("action", "content_type", "created_at")
    ordering = ("-created_at",)
    actions = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        # The scoped audit history is discoverable on the admin index for
        # every active actor; site staff eligibility stays with Django and
        # the queryset decides which events are actually visible.
        return is_active_actor(request.user)

    def has_view_permission(self, request, obj=None):
        if not is_active_actor(request.user):
            return False
        if obj is None:
            # Class/list admission for active actors; the scoped queryset
            # and per-event decision decide which rows are visible.
            return True
        if is_admin(request.user):
            return True
        target = obj.content_object
        if target is None or model_policy(type(target)) is None:
            return False
        return decide(request.user, "view_review_activity", target).allowed

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        if not is_active_actor(user):
            return queryset.none()
        if is_admin(user):
            return queryset

        filters = []
        for label in REVIEWABLE_MODELS:
            model = apps.get_model(label)
            if model is None:
                continue
            policy = model_policy(model)
            if policy is None or policy.kind != KIND_REVIEWABLE:
                continue
            ct = ContentType.objects.get_for_model(model)
            # Own and directly/group-shared root history; model moderators
            # additionally see everything the core visibility exposes,
            # including public archived history.
            roots = scope_queryset(user, model._base_manager.all(), "private")
            if is_moderator(user, model):
                roots = roots | visible_queryset(user, model._base_manager.all())
            filters.append(
                Q(
                    content_type=ct,
                    object_id__in=roots.values("pk"),
                )
            )
        if not filters:
            return queryset.none()
        return queryset.filter(reduce(or_, filters))
