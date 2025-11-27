import os

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

INITIALIZATION_DEPENDENCIES = ["users"]


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the utils app exists.
    Idempotent: safe to run multiple times.

    Creates the default owner user (from DEFAULT_OBJECT_OWNER_USERNAME if set,
    else ADMIN_USERNAME environment variable).

    Note: Moderation permissions (can_moderate_<model>) are created automatically
    by the post_migrate signal in utils/object_management/signals.py, not here.

    Returns:
        dict: Contains 'default_owner' User instance
    """
    admin_username = os.environ.get("ADMIN_USERNAME")
    owner_username = getattr(settings, "DEFAULT_OBJECT_OWNER_USERNAME", admin_username)

    if not owner_username:
        raise RuntimeError(
            "Neither DEFAULT_OBJECT_OWNER_USERNAME in settings nor ADMIN_USERNAME env var is set."
        )

    try:
        default_owner = User.objects.get(username=owner_username)
    except User.DoesNotExist:
        default_owner = User(
            is_active=True,
            is_superuser=(owner_username == admin_username),
            is_staff=(owner_username == admin_username),
            username=owner_username,
            email="",
            last_login=timezone.now(),
        )
        default_owner.set_unusable_password()
        default_owner.save()

    if stdout:
        print(
            f"Ensured default owner '{owner_username}' exists.",
            file=stdout,
        )

    return {"default_owner": default_owner}
