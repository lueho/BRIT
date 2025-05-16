"""
Initial data setup for the utils.properties app.
Implements autodiscovery-compatible ensure_initial_data().
"""
INITIALIZATION_DEPENDENCIES = ['users']

from users.utils import get_default_owner
from .models import Unit

def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the utils.properties app exists.
    Idempotent: safe to run multiple times.
    Creates the "No unit" unit for the default owner.
    """
    owner = get_default_owner()
    no_unit, _ = Unit.objects.get_or_create(owner=owner, name='No unit', defaults={"dimensionless": True})
    if stdout:
        print(f"Ensured unit 'No unit' for owner '{owner.username}' exists.", file=stdout)
    return {'no_unit': no_unit}
