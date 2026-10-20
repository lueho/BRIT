from django.conf import settings
from django.utils import timezone

from utils.object_management.models import get_default_owner

INITIALIZATION_DEPENDENCIES = ["object_management"]


def _ensure_dimensionless_unit(owner, name):
    from .models import Unit

    unit, created = Unit.objects.get_or_create(
        owner=owner, name=name, defaults={"dimensionless": True}
    )
    if not created and not unit.dimensionless:
        unit.dimensionless = True
        unit.save(update_fields=["dimensionless"])
    return unit


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the utils.properties app exists.
    Idempotent: safe to run multiple times.
    Creates the "No unit" unit, the configured default unit
    (``DEFAULT_NO_UNIT_NAME``) and the "number of collection points" property
    for the default owner.
    """
    from .models import Property

    owner = get_default_owner()
    no_unit = _ensure_dimensionless_unit(owner, "No unit")
    default_unit_name = getattr(settings, "DEFAULT_NO_UNIT_NAME", "No unit")
    if default_unit_name != no_unit.name:
        _ensure_dimensionless_unit(owner, default_unit_name)
    if not Property.objects.filter(
        owner=owner, name="number of collection points"
    ).exists():
        point_property = Property.objects.create(
            owner=owner,
            name="number of collection points",
            publication_status="published",
            approved_at=timezone.now(),
            approved_by=owner,
        )
        point_property.allowed_units.add(no_unit)
    if stdout:
        print(
            f"Ensured unit 'No unit' for owner '{owner.username}' exists.", file=stdout
        )
    return {"no_unit": no_unit}
