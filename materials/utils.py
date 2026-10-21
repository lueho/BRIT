from django.conf import settings
from django.utils import timezone

from utils.object_management.models import get_default_owner

from .models import MaterialCategory, MaterialComponent, MaterialComponentGroup

INITIALIZATION_DEPENDENCIES = ["object_management"]


def ensure_initial_data(stdout=None):
    """
    Standard entrypoint function for ensuring all initial data for the materials app exists.
    This function follows the autodiscovery pattern used by the ensure_initial_data management command.

    Args:
        stdout: Optional output stream for logging messages (if provided)

    Returns:
        dict: Dictionary with information about created data
    """
    if stdout:
        stdout.write("Ensuring base materials exist...")

    owner = get_default_owner()

    group_name = getattr(
        settings, "DEFAULT_MATERIALCOMPONENTGROUP_NAME", "Total Material"
    )
    group, _ = MaterialComponentGroup.objects.get_or_create(
        name=group_name, defaults={"owner": owner}
    )

    component_name = getattr(
        settings, "DEFAULT_MATERIALCOMPONENT_NAME", "Fresh Matter (FM)"
    )
    component, _ = MaterialComponent.objects.get_or_create(
        name=component_name, defaults={"owner": owner}
    )

    other_component_name = getattr(settings, "DEFAULT_OTHER_MATERIAL_NAME", "Other")
    other_component, _ = MaterialComponent.objects.get_or_create(
        name=other_component_name, defaults={"owner": owner}
    )

    if not MaterialCategory.objects.filter(name="Product", owner=owner).exists():
        MaterialCategory.objects.create(
            name="Product",
            description=(
                "A product is the output of a production process and is "
                "intentionally created from one or more materials to fulfil "
                "a specific function. It is a good with an intended positive "
                "market value."
            ),
            publication_status="published",
            approved_at=timezone.now(),
            approved_by=owner,
            owner=owner,
        )

    if stdout:
        stdout.write(f'Ensured component group "{group.name}" exists')
        stdout.write(f'Ensured component "{component.name}" exists')
        stdout.write(f'Ensured component "{other_component.name}" exists')

    return {
        "default_group": group,
        "default_component": component,
        "other_component": other_component,
    }
