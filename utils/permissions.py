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


class HasModelPermission(permissions.BasePermission):
    """
    A custom permission class that extends the base permission class provided by Django REST Framework.

    This class is used to check if a request should be granted or denied access based on the user's permissions and the
    required permissions for the view's action. It supports checking multiple permissions for a single action.
    """

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
