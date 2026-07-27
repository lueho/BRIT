"""Permissions for the population import API."""

from rest_framework.permissions import BasePermission

IMPORT_PERMISSIONS = (
    "population.add_populationobservation",
    "population.change_populationobservation",
)


class CanImportPopulation(BasePermission):
    """Only users granted add/change on population observations may import."""

    message = "You do not have permission to import population data."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return all(user.has_perm(perm) for perm in IMPORT_PERMISSIONS)
