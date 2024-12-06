from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions


class IsStaffOrReadOnly(permissions.BasePermission):
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
    """

    def has_permission(self, request, view):
        # Allow any user to list or retrieve public objects
        if getattr(view, 'action', None) in ['list', 'retrieve']:
            return True

        # Allow authenticated users to create objects
        if getattr(view, 'action', None) == 'create':
            return request.user and request.user.is_authenticated

        # For other actions, ensure the user is authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Handle safe methods
        if request.method in permissions.SAFE_METHODS:
            return self._check_safe_permissions(request, obj)

        # Handle write methods
        user = request.user

        if obj.owner == user:
            # If 'publication_status' is being modified, ensure the user is a moderator
            if 'publication_status' in request.data:
                if not self._is_moderator(user, obj):
                    return False
            return True  # Owners can modify other fields

        # Check if user is a moderator
        if self._is_moderator(user, obj):
            # Moderators cannot modify 'private' objects unless they are the owner
            if getattr(obj, 'publication_status', None) == 'private' and obj.owner != user:
                return False
            return True

        return False

    def _check_safe_permissions(self, request, obj):
        """
        Helper method to handle safe method permissions based on publication_status.
        """
        if not hasattr(obj, 'publication_status'):
            return False  # Deny access if publication_status is undefined

        if obj.publication_status == 'published':
            return True
        elif obj.publication_status == 'review':
            return obj.owner == request.user or self._is_moderator(request.user, obj)
        elif obj.publication_status == 'private':
            return obj.owner == request.user

        return False

    def _is_moderator(self, user, obj):
        """
        Determines if the user has moderation permissions for the given object.
        Assumes that a permission named 'can_moderate_<modelname>' exists.
        """
        model_name = obj._meta.model_name
        perm_codename = f'can_moderate_{model_name}'
        app_label = obj._meta.app_label
        return user.is_staff or user.has_perm(f'{app_label}.{perm_codename}')


class HasModelPermission(permissions.BasePermission):
    """
    A custom permission class that extends the base permission class provided by Django REST Framework.

    This class is used to check if a request should be granted or denied access based on the user's permissions and the
    required permissions for the view's action. It supports checking multiple permissions for a single action.
    """

    # TODO: EOL this class

    def has_permission(self, request, view):

        # The OPTIONS method is not associated with any action and should always be allowed
        if request.method in ('OPTIONS', 'HEAD'):
            return True

        if not hasattr(view, 'permission_required'):
            raise ImproperlyConfigured("View does not have a 'permission_required' attribute.")

        if not type(view.permission_required) is dict:
            raise ImproperlyConfigured("View's 'permission_required' attribute must be a dictionary.")

        if view.action not in view.permission_required:
            raise ImproperlyConfigured(f"Action '{view.action}' does not have a permission_required attribute.")

        required_permissions = view.permission_required.get(view.action)

        if required_permissions is None:
            return True

        if isinstance(required_permissions, str):
            required_permissions = [required_permissions]

        for perm in required_permissions:
            if not request.user.has_perm(perm):
                return False

        return True
