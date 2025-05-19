from django.conf import settings

from utils.models import get_default_owner

from .models import MaterialComponent, MaterialComponentGroup

INITIALIZATION_DEPENDENCIES = ["users"]


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

    if stdout:
        stdout.write(f'Ensured component group "{group.name}" exists')
        stdout.write(f'Ensured component "{component.name}" exists')
        stdout.write(f'Ensured component "{other_component.name}" exists')

    return {
        "default_group": group,
        "default_component": component,
        "other_component": other_component,
    }
