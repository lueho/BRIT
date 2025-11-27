"""
Automatic Permission Creation for UserCreatedObject Models

This module provides signal handlers that automatically create and manage
moderation permissions for all UserCreatedObject subclasses in the project.

## Overview

When Django runs migrations, this signal handler:
1. Discovers all concrete (non-abstract) UserCreatedObject subclasses
2. Creates a `can_moderate_<model>` permission for each model
3. Assigns these permissions to the moderators group

## Permission Naming

Permissions follow a consistent naming pattern:
- Codename: `can_moderate_<model_name>` (e.g., "can_moderate_collection")
- Name: "Can moderate <verbose_name_plural>" (e.g., "Can moderate collections")

## Configuration

- Group name: Set via `settings.REVIEW_MODERATORS_GROUP_NAME` (default: "moderators")
- The signal runs in all environments (dev, production, and tests)
- Uses get_or_create() for idempotency - safe to run multiple times

## Usage in Tests

Tests should FETCH permissions, not create them:

    # ✅ Correct
    permission = Permission.objects.get(
        codename="can_moderate_mymodel",
        content_type=content_type,
    )

    # ❌ Wrong - will cause IntegrityError
    # permission = Permission.objects.create(...)

## Architecture

The permission creation is centralized here (single source of truth) and used by:
- UserCreatedObjectPermission class (DRF permissions)
- UserCreatedObject querysets (filtering reviewable items)
- Views and mixins (access control)
- Templates (button visibility via templatetags)

Staff users always have moderation rights and don't need explicit permissions.

See Also:
- docs/02_developer_guide/user_created_objects.md
- utils/object_management/README.md
- utils/object_management/permissions.py
"""

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver


def _iter_user_created_models():
    """Yield all concrete, non-proxy models that inherit from UserCreatedObject."""
    try:
        from utils.object_management.models import UserCreatedObject
    except Exception:
        return

    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            try:
                if (
                    isinstance(model, type)
                    and issubclass(model, UserCreatedObject)
                    and not model._meta.abstract
                ):
                    yield model
            except Exception:
                # Be defensive; skip any model that causes problems during import/meta access
                continue


@receiver(post_migrate)
def ensure_moderation_permissions(sender, **kwargs):
    """
    After migrations, ensure custom per-model moderation permissions exist and
    are assigned to the moderators group.

    Runs in all environments (including tests) to ensure permissions exist
    consistently. Uses get_or_create for idempotency.
    """
    group_name = getattr(settings, "REVIEW_MODERATORS_GROUP_NAME", "moderators")

    try:
        moderators_group, _ = Group.objects.get_or_create(name=group_name)
    except Exception:
        # If group creation fails, don't break migrations
        return

    for model in _iter_user_created_models():
        try:
            model_name = model._meta.model_name
            app_label = model._meta.app_label
            content_type = ContentType.objects.get_for_model(
                model, for_concrete_model=False
            )
            codename = f"can_moderate_{model_name}"
            perm_name = f"Can moderate {model._meta.verbose_name_plural}"

            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=codename,
                defaults={"name": perm_name},
            )

            # Ensure the group holds the permission
            moderators_group.permissions.add(permission)
        except Exception:
            # Be robust; a single failure should not break overall signal execution
            continue
