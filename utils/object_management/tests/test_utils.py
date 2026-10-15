import os
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings

from sources.waste_collection.models import Collection
from utils.object_management import signals
from utils.object_management import utils as obj_utils


class ObjectManagementInitialDataTests(TestCase):
    def test_missing_env_variables_raises_runtime_error(self):
        """ensure_initial_data should fail if no usernames are configured."""
        with override_settings(DEFAULT_OBJECT_OWNER_USERNAME=None):
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(RuntimeError):
                    obj_utils.ensure_initial_data()


class ModerationPermissionSignalTests(TestCase):
    """The post-migrate signal only ensures can_moderate_* permission rows for
    registered reviewable models; it never touches groups or users."""

    def test_repeated_invocation_is_idempotent(self):
        signals.ensure_moderation_permissions(sender=None, using="default")
        first_count = Permission.objects.filter(
            codename__startswith="can_moderate_"
        ).count()
        signals.ensure_moderation_permissions(sender=None, using="default")
        self.assertEqual(
            Permission.objects.filter(codename__startswith="can_moderate_").count(),
            first_count,
        )

    def test_recreates_deleted_permission(self):
        content_type = ContentType.objects.get_for_model(Collection)
        Permission.objects.filter(
            codename="can_moderate_collection", content_type=content_type
        ).delete()
        signals.ensure_moderation_permissions(sender=None, using="default")
        self.assertTrue(
            Permission.objects.filter(
                codename="can_moderate_collection", content_type=content_type
            ).exists()
        )

    def test_ignores_senders_from_other_apps(self):
        content_type = ContentType.objects.get_for_model(Collection)
        Permission.objects.filter(
            codename="can_moderate_collection", content_type=content_type
        ).delete()
        signals.ensure_moderation_permissions(
            sender=SimpleNamespace(name="bibliography"), using="default"
        )
        self.assertFalse(
            Permission.objects.filter(
                codename="can_moderate_collection", content_type=content_type
            ).exists()
        )

    def test_does_not_create_groups_or_assign_permissions(self):
        groups_before = list(Group.objects.values_list("name", flat=True))
        signals.ensure_moderation_permissions(sender=None, using="default")
        self.assertEqual(
            list(Group.objects.values_list("name", flat=True)), groups_before
        )
