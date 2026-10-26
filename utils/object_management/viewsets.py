from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import UserCreatedObject
from .permissions import (
    GlobalObjectPermission,
    UserCreatedObjectPermission,
    apply_scope_filter,
    filter_queryset_for_user,
)
from .policy import decide
from .registry import (
    KIND_OWNED,
    KIND_REVIEWABLE,
    generated_profile,
    model_policy,
    resolve_create_parent,
    resolve_parent,
    resolve_parents,
)
from .services import (
    StaleRevisionError,
    content_mutation,
    perform_transition,
    record_creation,
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
    """Final authorization boundary for bound creates.

    For owned children and independent evidence models the validated parent
    context is resolved from the declared ``parent_path`` and the create
    decision is re-evaluated with it; missing or unauthorized context raises
    ``PermissionDenied`` before any row is written.

    Returns ``(policy, parent)`` so callers can scope the write boundary.
    """
    model = _serializer_model(view, serializer)
    policy = model_policy(model)
    if policy is None or policy.parent_path is None:
        return policy, None
    parent = _create_parent(view, serializer, policy)
    if parent is None:
        raise PermissionDenied("Creation requires a valid parent context.")
    decision = decide(view.request.user, "create", model, parent=parent)
    if not decision.allowed:
        raise PermissionDenied(decision.reason)
    return policy, parent


class GlobalObjectViewSet(ModelViewSet):
    """
    Base viewset for Global Objects.
    Implements read and write permissions.
    Read: Any user (authenticated or not)
    Write: Only staff users
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

        Objects the user may not read resolve to 404; readable objects still go
        through ``check_object_permissions`` for the requested action.
        """
        from django.shortcuts import get_object_or_404

        base_qs = filter_queryset_for_user(self.queryset, self.request.user)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        obj = get_object_or_404(base_qs, **{self.lookup_field: lookup_value})
        # Enforce object-level permissions after fetching from the base queryset
        self.check_object_permissions(self.request, obj)
        return obj

    def _save_uco_create(self, serializer):
        return serializer.save(
            owner=self.request.user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def perform_create(self, serializer):
        """Server owns owner/lifecycle initialization; payload cannot forge them."""
        validated = getattr(serializer, "validated_data", None)
        if isinstance(validated, dict):
            validated.pop("owner", None)
            validated.pop("publication_status", None)
        policy, parent = perform_policy_create(self, serializer)
        serializer_model = _serializer_model(self, serializer)
        if isinstance(validated, dict):
            # Generated-projection marker and source pointer are
            # server-controlled; a public create can only produce raw rows.
            profile = generated_profile(serializer_model)
            if profile is not None:
                for profile_field in profile:
                    validated.pop(profile_field, None)
        if not (
            isinstance(serializer_model, type)
            and issubclass(serializer_model, UserCreatedObject)
        ):
            serializer.save()
            return
        if policy is not None and policy.kind == KIND_OWNED and parent is not None:
            with content_mutation(self.request.user, parent, action="edit"):
                self._save_uco_create(serializer)
            return
        with transaction.atomic():
            obj = self._save_uco_create(serializer)
            record_creation(self.request.user, obj)

    def perform_update(self, serializer):
        instance = serializer.instance
        policy = model_policy(type(instance))
        proposed_parent = None
        if (
            policy is not None
            and policy.kind == KIND_REVIEWABLE
            and policy.parent_path is not None
        ):
            parent_field = policy.parent_path.split("__")[0]
            validated = getattr(serializer, "validated_data", None) or {}
            if parent_field in validated:
                new_parent = resolve_create_parent(policy, validated_data=validated)
                if new_parent is None:
                    raise ValidationError("invalid_parent")
                if isinstance(new_parent, (list, tuple)):
                    new_keys = sorted(getattr(p, "pk", None) for p in new_parent)
                    old_keys = sorted(
                        p.pk for p in resolve_parents(instance, policy.parent_path)
                    )
                    if new_keys != old_keys:
                        proposed_parent = new_parent
                else:
                    old_parent = resolve_parent(instance, policy.parent_path)
                    if getattr(new_parent, "pk", None) != getattr(
                        old_parent, "pk", None
                    ):
                        proposed_parent = new_parent
        with content_mutation(
            self.request.user,
            instance,
            action="edit",
            proposed_parent=proposed_parent,
        ) as fresh:
            serializer.instance = fresh
            serializer.save()

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
