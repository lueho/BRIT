from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import UserCreatedObject
from .permissions import (
    GlobalObjectPermission,
    UserCreatedObjectPermission,
    _forbidden_write_fields,
    apply_scope_filter,
    filter_queryset_for_user,
)
from .policy import decide
from .registry import (
    KIND_OWNED,
    KIND_REVIEWABLE,
    allows_unattached_create,
    declared_parent_changed,
    model_policy,
    resolve_create_parent,
)
from .services import (
    StaleRevisionError,
    _fresh_actor,
    authorize_create,
    content_mutation,
    perform_transition,
    record_creation,
    validate_created_parent,
    validate_references,
)


def _serializer_model(view, serializer):
    model = getattr(getattr(serializer, "Meta", None), "model", None)
    if model is None:
        queryset = getattr(view, "queryset", None)
        model = getattr(queryset, "model", None)
    return model


def _create_parent(view, serializer, policy):
    get_policy_parent = getattr(view, "get_policy_parent", None)
    parent = get_policy_parent() if callable(get_policy_parent) else None
    if parent is None:
        parent = resolve_create_parent(
            policy, validated_data=getattr(serializer, "validated_data", None)
        )
    return parent


def perform_policy_create(view, serializer):
    """Advisory create-context resolution for bound creates.

    Resolves the registered policy and declared ``parent_path`` parent context
    and performs a preliminary ``create`` decision for early denial. The
    authoritative check runs inside the write boundary via
    ``services.authorize_create`` with a freshly reloaded actor and parent
    rows; this advisory step never substitutes for it.

    Returns ``(policy, parent)`` so callers can scope the write boundary.
    """
    model = _serializer_model(view, serializer)
    policy = model_policy(model)
    if policy is None:
        return policy, None
    parent = None
    if policy.parent_path is not None:
        parent = _create_parent(view, serializer, policy)
        if parent is None and not allows_unattached_create(model):
            raise PermissionDenied("Creation requires a valid parent context.")
    decision = decide(view.request.user, "create", model, parent=parent)
    if not decision.allowed:
        raise PermissionDenied(decision.reason)
    return policy, parent


def finalize_policy_create(view, serializer, policy, parent):
    """Persist a governed create inside the shared write boundary.

    Owned children are written inside a ``content_mutation`` on the resolved
    parent so the parent's audit captures the new row; only real
    ``UserCreatedObject`` rows get owner/lifecycle injection and creation
    audit events. Unregistered non-UCO models keep plain serializer
    persistence with reference validation.
    """
    model = _serializer_model(view, serializer)
    is_uco = isinstance(model, type) and issubclass(model, UserCreatedObject)
    if is_uco and policy is None:
        raise PermissionDenied("Unregistered model cannot be created.")
    validated = getattr(serializer, "validated_data", None)
    if policy is not None and isinstance(validated, dict):
        for forbidden in _forbidden_write_fields(model):
            validated.pop(forbidden, None)
    if policy is not None and policy.kind == KIND_OWNED and parent is not None:
        with content_mutation(
            view.request.user, parent, action="edit"
        ) as locked_parent:
            actor = authorize_create(view.request.user, model, parent=locked_parent)
            view.request.user = actor
            validate_references(actor, validated)
            if is_uco:
                obj = serializer.save(
                    owner=actor,
                    publication_status=UserCreatedObject.STATUS_PRIVATE,
                )
            else:
                obj = serializer.save()
            validate_created_parent(obj, parent=locked_parent)
            return obj
    with transaction.atomic():
        if policy is not None:
            actor = authorize_create(view.request.user, model, parent=parent)
        else:
            actor = _fresh_actor(view.request.user)
        view.request.user = actor
        validate_references(actor, validated)
        if is_uco:
            obj = serializer.save(
                owner=actor,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            validate_created_parent(obj, parent=parent)
            record_creation(actor, obj)
            return obj
        created = serializer.save()
        validate_created_parent(created, parent=parent)
        return created


def perform_policy_update(view, serializer):
    """Shared governed-update boundary for bound serializers.

    Resolves a changed declared evidence parent through
    ``resolve_create_parent``/``resolve_parents``, hands the reparent to
    ``content_mutation`` via ``proposed_parent``, rebinds
    ``serializer.instance`` to the yielded fresh row, validates reference read
    access inside the locked write boundary, and saves once. Non-governed
    instances keep ordinary serializer behavior.
    """
    instance = getattr(serializer, "instance", None)
    policy = model_policy(type(instance)) if isinstance(instance, Model) else None
    if policy is None and not isinstance(instance, UserCreatedObject):
        serializer.save()
        return
    proposed_parent = None
    if (
        policy is not None
        and policy.kind in (KIND_REVIEWABLE, KIND_OWNED)
        and policy.parent_path is not None
    ):
        parent_field = policy.parent_path.split("__")[0]
        validated = getattr(serializer, "validated_data", None) or {}
        if parent_field in validated:
            new_parent = resolve_create_parent(policy, validated_data=validated)
            if new_parent is None:
                raise ValidationError("invalid_parent")
            if declared_parent_changed(instance, policy.parent_path, new_parent):
                proposed_parent = new_parent
    with content_mutation(
        view.request.user,
        instance,
        action="edit",
        proposed_parent=proposed_parent,
    ) as fresh:
        serializer.instance = fresh
        actor = _fresh_actor(view.request.user)
        view.request.user = actor
        validate_references(actor, getattr(serializer, "validated_data", None))
        serializer.save()


class GlobalObjectViewSet(ModelViewSet):
    """
    Base viewset for Global Objects.
    Implements read and write permissions.
    Read: Any user (authenticated or not)
    Write: users with the explicit administer_objects capability
    """

    permission_classes = [GlobalObjectPermission]


class UserCreatedObjectViewSet(viewsets.ModelViewSet):
    """
    Base viewset for all user-created objects.
    Implements generic permissions and common actions.
    """

    permission_classes = [UserCreatedObjectPermission]
    serializer_class = None  # Must be set in the concrete viewset
    queryset = None  # Must be set in the concrete viewset

    def get_queryset(self):
        """Return a queryset filtered according to user permissions and scope parameter.

        Delegates to ``policy.scope_queryset``: a missing scope returns the
        read-visible set; an unknown scope returns no rows.
        """
        user = self.request.user
        queryset = self.queryset
        scope = self.request.query_params.get("scope")

        if scope is None:
            return filter_queryset_for_user(queryset, user)
        return apply_scope_filter(queryset, scope, user=user)

    def get_object(self):
        """Retrieve a single object from the read-scoped queryset, then enforce
        object-level permissions.

        Objects the user may not read resolve to 404 instead of leaking existence; the
        object-level permission check still gates the requested action.
        """
        from django.shortcuts import get_object_or_404

        base_qs = filter_queryset_for_user(self.queryset, self.request.user)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        obj = get_object_or_404(base_qs, **{self.lookup_field: lookup_value})
        # Enforce object-level permissions after fetching from the base queryset
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        """Server owns owner/lifecycle initialization; payload cannot forge them."""
        policy, parent = perform_policy_create(self, serializer)
        finalize_policy_create(self, serializer, policy, parent)

    def perform_update(self, serializer):
        perform_policy_update(self, serializer)

    def perform_destroy(self, instance):
        with content_mutation(self.request.user, instance, action="delete") as locked:
            locked.delete()

    def _get_comment(self, request) -> str:
        try:
            payload = request.data
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            return (payload.get("comment") or payload.get("message") or "").strip()
        return ""

    def _get_expected_revision(self, request):
        try:
            payload = request.data
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            return payload.get("expected_revision")
        return None

    def _transition_response(self, request, obj, policy_action, message):
        try:
            perform_transition(
                request.user,
                obj,
                policy_action,
                expected_revision=self._get_expected_revision(request),
                comment=self._get_comment(request),
                cascade=True,
            )
        except StaleRevisionError as e:
            return Response(
                {"error": str(e.messages[0] if e.messages else e)},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"status": f"{self.queryset.model.__name__} {message}"},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True, methods=["post"], permission_classes=[UserCreatedObjectPermission]
    )
    def register_for_review(self, request, pk=None):
        """
        Allows owners to register an object for review.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        permission = UserCreatedObjectPermission()
        if not permission.has_submit_permission(request, obj):
            return Response(
                {
                    "error": "You do not have permission to submit this object for review."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._transition_response(
            request, obj, "submit", "has been submitted for review."
        )

    @action(
        detail=True, methods=["post"], permission_classes=[UserCreatedObjectPermission]
    )
    def withdraw_from_review(self, request, pk=None):
        """
        Allows owners to withdraw an object from review.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        permission = UserCreatedObjectPermission()
        if not permission.has_withdraw_permission(request, obj):
            return Response(
                {
                    "error": "You do not have permission to withdraw this object from review."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._transition_response(
            request, obj, "withdraw", "has been withdrawn from review."
        )

    @action(
        detail=True, methods=["post"], permission_classes=[UserCreatedObjectPermission]
    )
    def approve(self, request, pk=None):
        """
        Approve an object in 'review' state.
        Only accessible to moderators.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        permission = UserCreatedObjectPermission()
        if not permission.has_approve_permission(request, obj):
            return Response(
                {"error": "You do not have permission to approve this object."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._transition_response(
            request, obj, "approve", "has been approved and is now published."
        )

    @action(
        detail=True, methods=["post"], permission_classes=[UserCreatedObjectPermission]
    )
    def reject(self, request, pk=None):
        """
        Reject an object in 'review' state.
        Only accessible to moderators.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        permission = UserCreatedObjectPermission()
        if not permission.has_reject_permission(request, obj):
            return Response(
                {"error": "You do not have permission to reject this object."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._transition_response(request, obj, "reject", "has been declined.")

    @action(
        detail=True, methods=["post"], permission_classes=[UserCreatedObjectPermission]
    )
    def archive(self, request, pk=None):
        """
        Archive a priviously published object.
        That marks is as outdated but it is still available for
        legacy analyses.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        permission = UserCreatedObjectPermission()
        if not permission.has_archive_permission(request, obj):
            return Response(
                {"error": "You do not have permission to archive this object."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._transition_response(request, obj, "archive", "has been archived.")
