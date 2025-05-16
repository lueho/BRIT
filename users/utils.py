"""
Initial data setup for the users app.
Implements autodiscovery-compatible ensure_initial_data().
"""
import os
from django.contrib.auth.models import Group, User
from django.utils import timezone

def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the users app exists.
    Idempotent: safe to run multiple times.
    Creates the 'registered' group and the admin user from env vars, and adds admin to group.
    """
    # 1. Ensure group exists
    registered, _ = Group.objects.get_or_create(name='registered')

    # 2. Ensure superuser exists
    username = os.environ['ADMIN_USERNAME']
    email = os.environ.get('ADMIN_EMAIL', '')
    password = os.environ.get('ADMIN_PASSWORD', None)
    try:
        superuser = User.objects.get(username=username)
    except User.DoesNotExist:
        superuser = User(
            is_active=True,
            is_superuser=True,
            is_staff=True,
            username=username,
            email=email,
            last_login=timezone.now(),
        )
        if password:
            superuser.set_password(password)
        superuser.save()

    # 3. Ensure superuser is in group
    superuser.groups.add(registered)

    if stdout:
        print(f"Ensured group 'registered' and superuser '{username}' exist.", file=stdout)

    return {'superuser': superuser, 'group': registered}


def get_default_owner():
    """
    Fetch the default owner user (admin). Never creates users.
    Raises RuntimeError if the user does not exist.
    """
    username = os.environ.get('ADMIN_USERNAME')
    owner, _ = User.objects.get_or_create(username=username)
    return owner
