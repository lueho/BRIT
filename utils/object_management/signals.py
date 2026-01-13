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
from django.core.cache import cache
from django.db.models.signals import post_delete, post_migrate, post_save
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


@receiver(post_save)
def clear_moderation_cache_on_save(sender, instance, **kwargs):
    """
    Clear moderation cache when UserCreatedObject instances are saved.

    Only clears cache when:
    - A new object is created
    - The publication_status field changes to/from 'review'

    This ensures pending review counts stay accurate without excessive cache clearing.
    """
    try:
        from utils.object_management.models import UserCreatedObject

        # Check if the sender is a UserCreatedObject subclass
        if not (
            isinstance(sender, type)
            and issubclass(sender, UserCreatedObject)
            and not sender._meta.abstract
        ):
            return

        created = kwargs.get("created", False)

        # Always clear cache for new objects (they might be in review status)
        if created:
            current_status = getattr(instance, "publication_status", None)
            if current_status == "review":
                _clear_moderator_caches()
            return

        # For updates, check if publication_status changed to/from 'review'
        # We need to detect status changes by checking the update_fields or
        # comparing with the database value
        update_fields = kwargs.get("update_fields")

        # If update_fields is specified and doesn't include publication_status, skip
        if update_fields is not None and "publication_status" not in update_fields:
            return

        # Check current status - if it's 'review' or was 'review', clear cache
        current_status = getattr(instance, "publication_status", None)
        if current_status == "review":
            _clear_moderator_caches()
        else:
            # The status might have changed FROM 'review' to something else
            # We can't easily detect this without tracking, so clear cache
            # when update_fields includes publication_status
            if update_fields is None or "publication_status" in update_fields:
                _clear_moderator_caches()

    except Exception:
        # Be defensive - if cache clearing fails, don't break the save operation
        pass


@receiver(post_delete)
def clear_moderation_cache_on_delete(sender, instance, **kwargs):
    """
    Clear moderation cache when UserCreatedObject instances are deleted.

    Only clears cache if the deleted object was in 'review' status,
    as that's the only status that affects pending review counts.
    """
    try:
        from utils.object_management.models import UserCreatedObject

        # Check if the sender is a UserCreatedObject subclass
        if not (
            isinstance(sender, type)
            and issubclass(sender, UserCreatedObject)
            and not sender._meta.abstract
        ):
            return

        # Only clear cache if the deleted object was in review status
        deleted_status = getattr(instance, "publication_status", None)
        if deleted_status == "review":
            _clear_moderator_caches()

    except Exception:
        # Be defensive - if cache clearing fails, don't break the delete operation
        pass


def _clear_moderator_caches():
    """Clear moderation cache for all users who might be moderators."""
    try:
        from django.contrib.auth.models import User
        from django.db.models import Q

        # Clear cache for staff users and users with moderation permissions
        moderator_users = User.objects.filter(
            Q(is_staff=True)
            | Q(
                groups__name=getattr(
                    settings, "REVIEW_MODERATORS_GROUP_NAME", "moderators"
                )
            )
        ).distinct()

        for user in moderator_users:
            cache_keys = [
                f"pending_review_count_{user.id}",
                f"is_moderator_any_model_{user.id}",
            ]
            for key in cache_keys:
                cache.delete(key)
    except Exception:
        # If cache clearing fails, it's not critical - cache will expire naturally
        pass


def _clear_user_moderator_cache(user_id):
    """Clear moderation cache for a specific user."""
    try:
        cache_keys = [
            f"pending_review_count_{user_id}",
            f"is_moderator_any_model_{user_id}",
        ]
        for key in cache_keys:
            cache.delete(key)
    except Exception:
        pass


@receiver(post_save, sender="auth.User")
def clear_user_cache_on_staff_change(sender, instance, **kwargs):
    """
    Clear user's moderator cache when their staff status changes.

    This ensures is_moderator_for_any_model stays accurate when
    a user becomes or stops being staff.
    """
    try:
        update_fields = kwargs.get("update_fields")
        # If update_fields is specified and doesn't include is_staff, skip
        if update_fields is not None and "is_staff" not in update_fields:
            return
        _clear_user_moderator_cache(instance.id)
    except Exception:
        pass


def _on_group_membership_change(sender, instance, action, pk_set, **kwargs):
    """
    Clear cache when users are added to or removed from the moderators group.

    This handles M2M changes for User.groups relationship.
    """
    if action not in ("post_add", "post_remove", "post_clear"):
        return

    try:
        moderators_group_name = getattr(
            settings, "REVIEW_MODERATORS_GROUP_NAME", "moderators"
        )

        # Check if the moderators group is involved
        if sender._meta.model_name == "user_groups":
            # instance is the User, pk_set contains Group IDs
            from django.contrib.auth.models import Group

            if action == "post_clear":
                # All groups removed - clear cache for this user
                _clear_user_moderator_cache(instance.id)
            elif pk_set:
                # Check if moderators group is in the changed groups
                moderators_group = Group.objects.filter(
                    name=moderators_group_name, pk__in=pk_set
                ).first()
                if moderators_group:
                    _clear_user_moderator_cache(instance.id)
    except Exception:
        pass


# Connect the M2M signal for User.groups
try:
    from django.contrib.auth.models import User
    from django.db.models.signals import m2m_changed

    m2m_changed.connect(
        _on_group_membership_change,
        sender=User.groups.through,
        dispatch_uid="clear_moderator_cache_on_group_change",
    )
except Exception:
    # If connection fails during import, it's not critical
    pass
