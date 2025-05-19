from utils.models import get_default_owner

INITIALIZATION_DEPENDENCIES = ["users"]


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the utils.properties app exists.
    Idempotent: safe to run multiple times.
    Creates the "No unit" unit for the default owner.
    """
    from .models import Unit

    owner = get_default_owner()
    no_unit, _ = Unit.objects.get_or_create(
        owner=owner, name="No unit", defaults={"dimensionless": True}
    )
    if stdout:
        print(
            f"Ensured unit 'No unit' for owner '{owner.username}' exists.", file=stdout
        )
    return {"no_unit": no_unit}
