import os

from django.contrib.auth.models import Group, User
from django.utils import timezone


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the users app exists.
    Idempotent: safe to run multiple times.
    Creates the 'registered' and 'analysis_api' groups and the admin user
    (from ADMIN_USERNAME).
    """
    # 1. Create group for registered users and the extended analysis API group
    registered, _ = Group.objects.get_or_create(name="registered")
    Group.objects.get_or_create(name="analysis_api")

    # 2. Create superuser (admin)
    admin_username = os.environ["ADMIN_USERNAME"]
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    admin_password = os.environ.get("ADMIN_PASSWORD", None)
    try:
        superuser = User.objects.get(username=admin_username)
    except User.DoesNotExist:
        superuser = User(
            is_active=True,
            is_superuser=True,
            is_staff=True,
            username=admin_username,
            email=admin_email,
            last_login=timezone.now(),
        )
        if admin_password:
            superuser.set_password(admin_password)
        superuser.save()

    # 3. Add superuser to the registered group
    superuser.groups.add(registered)

    if stdout:
        print(
            f"Ensured groups 'registered', 'analysis_api', and superuser "
            f"'{admin_username}' exist.",
            file=stdout,
        )

    return {"superuser": superuser, "group": registered}
