"""Permissions for the NUTS vintage import API."""

from rest_framework.permissions import BasePermission

IMPORT_PERMISSIONS = (
    "maps.add_nutsregion",
    "maps.change_nutsregion",
)


class CanImportNutsRegions(BasePermission):
    """Only users granted add/change on NUTS regions may import a vintage."""

    message = "You do not have permission to import NUTS regions."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return all(user.has_perm(perm) for perm in IMPORT_PERMISSIONS)
