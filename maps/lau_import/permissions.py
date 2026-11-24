"""Permissions for the LAU vintage import API."""

from rest_framework.permissions import BasePermission

IMPORT_PERMISSIONS = (
    "maps.add_lauregion",
    "maps.change_lauregion",
)


class CanImportLauRegions(BasePermission):
    """Only users granted add/change on LAU regions may import a vintage."""

    message = "You do not have permission to import LAU regions."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return all(user.has_perm(perm) for perm in IMPORT_PERMISSIONS)
