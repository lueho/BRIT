"""
Utility functions for creating and managing initial data for the materials app.
"""
from django.conf import settings
from users.utils import get_default_owner

from .models import MaterialComponent, MaterialComponentGroup

# Define dependencies - materials depends on users being initialized first
INITIALIZATION_DEPENDENCIES = ['users']


def ensure_base_materials():
    """
    Ensure all base materials required by the application exist.
    This includes the default component group and material components.
    
    Returns:
        tuple: A tuple containing (default_group, default_component)
    """
    owner = get_default_owner()
    
    # Create or get the default component group
    group_name = getattr(settings, 'DEFAULT_MATERIALCOMPONENTGROUP_NAME', 'Total Material')
    group, group_created = MaterialComponentGroup.objects.get_or_create(
        name=group_name,
        defaults={'owner': owner}
    )
    
    # Create or get the default material component
    component_name = getattr(settings, 'DEFAULT_MATERIALCOMPONENT_NAME', 'Fresh Matter (FM)')
    component, component_created = MaterialComponent.objects.get_or_create(
        name=component_name,
        defaults={'owner': owner}
    )

    # Ensure 'Other' component exists
    other_component, other_created = MaterialComponent.objects.get_or_create(
        name='Other',
        defaults={'owner': owner}
    )
    
    return group, component


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
        stdout.write('Ensuring base materials exist...')
    
    # Ensure base materials exist
    group, component = ensure_base_materials()
    
    if stdout:
        stdout.write(f'Ensured component group "{group.name}" exists')
        stdout.write(f'Ensured component "{component.name}" exists')
    
    # Return data summary
    return {
        'default_group': group,
        'default_component': component,
    }


def get_default_component_group():
    """
    Get the default component group. Creates it if it doesn't exist.
    
    Returns:
        MaterialComponentGroup: The default component group
    """
    group, _ = ensure_base_materials()
    return group


# Alias for compatibility with older code
def get_default_group():
    """
    Alias for get_default_component_group() for compatibility.
    
    Returns:
        MaterialComponentGroup: The default component group
    """
    return get_default_component_group()


def get_default_component():
    """
    Get the default material component. Creates it if it doesn't exist.
    
    Returns:
        MaterialComponent: The default component
    """
    _, component = ensure_base_materials()
    return component
