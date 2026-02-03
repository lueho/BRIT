import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import ReviewAction
from .permissions import GlobalObjectPermission, UserCreatedObjectPermission

logger = logging.getLogger(__name__)


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

        Supports query parameter:
        - scope: Different filtering options for objects
          'published' - Only published objects (default)
          'private' - Only user's own objects
          'review' - User's own objects or objects in review
        """
        user = self.request.user
        queryset = self.queryset
        scope = self.request.query_params.get("scope", "published")

        # Staff users see all objects without filtering
        if user.is_staff:
            return queryset

        # Unauthenticated users only see published objects
        if not user.is_authenticated:
            return queryset.filter(publication_status="published")

        # Handle different scopes for authenticated non-staff users
        if scope == "private":
            # Private scope: only user's own objects
            return queryset.filter(owner=user)
        elif scope == "review":
            # Review scope: user's own objects or objects in review
            q_owner = Q(owner=user)
            q_review = Q(publication_status="review")
            return queryset.filter(q_owner | q_review)
        elif scope == "published":
            # Published scope: only published objects
            return queryset.filter(publication_status="published")
        else:
            # Default behavior for invalid scope: same as no scope
            # See user's own objects and published objects
            return queryset.filter(Q(owner=user) | Q(publication_status="published"))

    def get_object(self):
        """
        Retrieve a single object by primary key without applying scope-based list filters,
        then enforce object-level permissions.

        Rationale: list-scoped filtering (e.g., scope=private) should not cause 404 on
        detail views when the user has permission to view the object. The object-level
        permission check performed by check_object_permissions will gate access
        appropriately (published: anyone; private/review/archived: owner/moderator/staff).
        """
        from django.shortcuts import get_object_or_404

        base_qs = self.queryset
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        obj = get_object_or_404(base_qs, **{self.lookup_field: lookup_value})
        # Enforce object-level permissions after fetching from the base queryset
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def _is_moderator(self, user, model):
        """
        Determines if the user has moderation permissions for the model.
        """
        perm_codename = f"can_moderate_{model._meta.model_name}"
        app_label = model._meta.app_label
        return user.has_perm(f"{app_label}.{perm_codename}") or user.is_staff

    def _get_comment(self, request) -> str:
        try:
            payload = request.data
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            return (payload.get("comment") or payload.get("message") or "").strip()
        return ""

    def _post_review_action(
        self,
        request,
        obj,
        action_name,
        review_action,
        previous_status=None,
    ):
        comment = self._get_comment(request)
        if review_action:
            try:
                ReviewAction.objects.create(
                    content_type=ContentType.objects.get_for_model(obj.__class__),
                    object_id=obj.pk,
                    user=request.user,
                    action=review_action,
                    comment=comment,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create ReviewAction for %s: %s", action_name, exc
                )

        cascade_handler = getattr(obj, "cascade_review_action", None)
        if not callable(cascade_handler):
            return

        try:
            cascade_handler(
                action_name=action_name,
                actor=getattr(request, "user", None),
                previous_status=previous_status,
            )
        except Exception as exc:
            logger.warning(
                "Review action cascade failed for %s: %s",
                obj,
                exc,
            )

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def register_for_review(self, request, pk=None):
        """
        Allows owners to register an object for review.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        try:
            previous_status = getattr(obj, "publication_status", None)
            obj.register_for_review()
            self._post_review_action(
                request,
                obj,
                action_name="submit_for_review",
                review_action=ReviewAction.ACTION_SUBMITTED,
                previous_status=previous_status,
            )
            return Response(
                {
                    "status": f"{self.queryset.model.__name__} has been submitted for review."
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def withdraw_from_review(self, request, pk=None):
        """
        Allows owners to withdraw an object from review.
        """
        obj = self.get_object()

        # Enforce object-level permissions
        self.check_object_permissions(request, obj)

        try:
            previous_status = getattr(obj, "publication_status", None)
            obj.withdraw_from_review()
            self._post_review_action(
                request,
                obj,
                action_name="withdraw_from_review",
                review_action=ReviewAction.ACTION_WITHDRAWN,
                previous_status=previous_status,
            )
            return Response(
                {
                    "status": f"{self.queryset.model.__name__} has been withdrawn from review."
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        try:
            previous_status = getattr(obj, "publication_status", None)
            obj.approve(
                user=request.user
            )  # Utilize the model's approve method for consistency
            self._post_review_action(
                request,
                obj,
                action_name="approve",
                review_action=ReviewAction.ACTION_APPROVED,
                previous_status=previous_status,
            )
            # TODO: Implement notification to the owner
            return Response(
                {
                    "status": f"{self.queryset.model.__name__} has been approved and is now published."
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        try:
            previous_status = getattr(obj, "publication_status", None)
            obj.reject()
            self._post_review_action(
                request,
                obj,
                action_name="reject",
                review_action=ReviewAction.ACTION_REJECTED,
                previous_status=previous_status,
            )
            # TODO: Implement notification to the owner
            return Response(
                {
                    "status": f"{self.queryset.model.__name__} has been rejected and is now private."
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        try:
            obj.archive()
            # TODO: Implement notification to the owner
            return Response(
                {
                    "status": f"{self.queryset.model.__name__} has been archived and is now private."
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
