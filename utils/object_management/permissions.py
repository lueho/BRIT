from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions
from rest_framework import exceptions as drf_exceptions


class GlobalObjectPermission(permissions.BasePermission):
    """
    Custom permission to allow read-only access to anyone,
    and write access only to staff users.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and request.user.is_authenticated and request.user.is_staff


class UserCreatedObjectPermission(permissions.BasePermission):
    """
    Generic permission class for user-created objects.
    Handles ownership, publication_status, and moderation permissions dynamically.

    Supports the review workflow with methods for checking if a user can:
    - submit_for_review: Only owners can submit their private objects for review
    - withdraw_from_review: Only owners can withdraw their objects from review
    - approve: Only moderators can approve objects in review
    - reject: Only moderators can reject objects in review
    """

    def has_permission(self, request, view):
        # Allow any user to list or retrieve public objects
        if getattr(view, "action", None) in ["list", "retrieve"]:
            return True

        # For create action, check proper model permissions
        if getattr(view, "action", None) == "create":
            # User must be authenticated
            if not (request.user and request.user.is_authenticated):
                return False

            # Staff users can always create objects
            if request.user.is_staff:
                return True

            # Get model from viewset's queryset
            try:
                model = view.get_queryset().model
                app_label = model._meta.app_label
                model_name = model._meta.model_name

                # Check if user has 'add' permission for this model
                return request.user.has_perm(f"{app_label}.add_{model_name}")
            except (AttributeError, Exception):
                # If we can't determine the model permission, default to False for security
                return False

        # For other actions, ensure the user is authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Handle safe methods
        if request.method in permissions.SAFE_METHODS:
            return self._check_safe_permissions(request, obj)

        # Handle write methods
        user = request.user

        if obj.owner == user:
            from .models import UserCreatedObject

            # Owners cannot modify objects that are already published or archived
            if getattr(obj, "publication_status", None) in (
                UserCreatedObject.STATUS_PUBLISHED,
                getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"),
            ):
                return False

            # Safely access request data (can raise UnsupportedMediaType for empty multipart)
            try:
                payload = request.data
            except drf_exceptions.UnsupportedMediaType:
                payload = {}

            # Four eyes principle: moderators cannot publish their own objects
            if (
                "publication_status" in payload
                and payload["publication_status"] == UserCreatedObject.STATUS_PUBLISHED
                and self._is_moderator(user, obj)
            ):
                return False

            # If attempting to change publication_status, require moderator rights
            if "publication_status" in payload and not self._is_moderator(user, obj):
                return False

            return True  # Owners can modify other fields

        # Check if user is a moderator
        if self._is_moderator(user, obj):
            # Moderators cannot modify 'private' objects unless they are the owner
            if (
                getattr(obj, "publication_status", None) == "private"
                and obj.owner != user
            ):
                return False
            # Moderators may only change 'publication_status'—nothing else
            if request.method in ("PATCH", "PUT"):
                try:
                    payload = request.data
                except Exception:
                    payload = {}
                # Only allow if the only field being changed is 'publication_status'
                allowed_fields = {"publication_status"}
                changed_fields = set(payload.keys())
                if not changed_fields.issubset(allowed_fields):
                    return False
            return True

        return False

    def _check_safe_permissions(self, request, obj):
        """
        Helper method to handle safe method permissions based on publication_status.
        """
        if not hasattr(obj, "publication_status"):
            return False  # Deny access if publication_status is undefined

        from .models import UserCreatedObject

        status = obj.publication_status

        # Published objects are always readable
        if status == UserCreatedObject.STATUS_PUBLISHED:
            return True

        # Objects in review: owner or moderator/staff can view
        if status == UserCreatedObject.STATUS_REVIEW:
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        # Private objects: owner or moderator/staff can view
        if status == UserCreatedObject.STATUS_PRIVATE:
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        # Archived objects: owner or moderator/staff can view
        if status == getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"):
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        return False

    def _is_moderator(self, user, obj):
        """
        Determines if the user has moderation permissions for the given object.
        Assumes that a permission named 'can_moderate_<modelname>' exists.
        """
        if not user or not user.is_authenticated:
            return False

        model_name = obj._meta.model_name
        perm_codename = f"can_moderate_{model_name}"
        app_label = obj._meta.app_label
        return user.is_staff or user.has_perm(f"{app_label}.{perm_codename}")

    def has_submit_permission(self, request, obj):
        """
        Check if the user can submit an object for review.
        Only owners can submit their private objects.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            obj.owner == request.user
            and obj.publication_status == UserCreatedObject.STATUS_PRIVATE
        )

    def has_withdraw_permission(self, request, obj):
        """
        Check if the user can withdraw an object from review.
        Only owners can withdraw their objects from review.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            obj.owner == request.user
            and obj.publication_status == UserCreatedObject.STATUS_REVIEW
        )

    def has_approve_permission(self, request, obj):
        """
        Check if the user can approve an object.
        Only moderators can approve objects in review.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            self._is_moderator(request.user, obj)
            and obj.publication_status == UserCreatedObject.STATUS_REVIEW
        )

    def has_reject_permission(self, request, obj):
        """
        Check if the user can reject an object.
        Only moderators can reject objects in review.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            self._is_moderator(request.user, obj)
            and obj.publication_status == UserCreatedObject.STATUS_REVIEW
        )
