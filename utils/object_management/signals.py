from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# We create per-model moderation permissions for all concrete subclasses of
# utils.object_management.models.UserCreatedObject and assign them to a
# configurable moderators group.
# - Permission codename format: can_moderate_<model_name>
# - Checked throughout the codebase in UserCreatedObjectPermission/_querysets/views/templates
# - Staff users implicitly have moderation rights and do not need the permission


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
                    and not model._meta.proxy
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

    Skips execution when running tests (settings.TESTING=True) to avoid
    colliding with tests that explicitly create these permissions.
    """
    # Avoid interfering with the project test suite which manages permissions explicitly
    if getattr(settings, "TESTING", False):
        return

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
            content_type = ContentType.objects.get_for_model(model)
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
