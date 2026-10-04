from utils.object_management.models import get_default_owner

INITIALIZATION_DEPENDENCIES = ["users", "utils.object_management"]


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the utils.properties app exists.
    Idempotent: safe to run multiple times.
    Creates the "No unit" unit for the default owner.
    """
    from .models import Unit

    owner = get_default_owner()
    no_unit, created = Unit.objects.get_or_create(
        owner=owner, name="No unit", defaults={"dimensionless": True}
    )
    if not created and not no_unit.dimensionless:
        no_unit.dimensionless = True
        no_unit.save(update_fields=["dimensionless"])
    if stdout:
        print(
            f"Ensured unit 'No unit' for owner '{owner.username}' exists.", file=stdout
        )
    return {"no_unit": no_unit}
