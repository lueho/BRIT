import os
from unittest import mock

from django.test import TestCase, override_settings

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
    def tearDown(self):
        signals._moderation_permissions_loaded.clear()
        super().tearDown()

    def test_signal_skips_repeated_successful_passes(self):
        signals._moderation_permissions_loaded.clear()
        model = mock.Mock()
        model._meta.model_name = "collection"
        model._meta.verbose_name_plural = "collections"
        moderators_group = mock.Mock()
        permission = mock.Mock()

        with (
            mock.patch(
                "utils.object_management.signals._iter_user_created_models",
                side_effect=lambda: iter([model]),
            ),
            mock.patch(
                "utils.object_management.signals.Group.objects.get_or_create",
                return_value=(moderators_group, False),
            ) as group_get_or_create,
            mock.patch(
                "utils.object_management.signals.ContentType.objects.get_for_model",
                return_value=mock.Mock(),
            ),
            mock.patch(
                "utils.object_management.signals.Permission.objects.get_or_create",
                return_value=(permission, False),
            ) as permission_get_or_create,
        ):
            signals.ensure_moderation_permissions(sender=None, using="default")
            signals.ensure_moderation_permissions(sender=None, using="default")

        self.assertEqual(group_get_or_create.call_count, 1)
        self.assertEqual(permission_get_or_create.call_count, 1)
        moderators_group.permissions.add.assert_called_once_with(permission)

    def test_signal_retries_after_incomplete_pass(self):
        signals._moderation_permissions_loaded.clear()
        model = mock.Mock()
        model._meta.model_name = "collection"
        model._meta.verbose_name_plural = "collections"
        moderators_group = mock.Mock()
        permission = mock.Mock()

        with (
            mock.patch(
                "utils.object_management.signals._iter_user_created_models",
                side_effect=lambda: iter([model]),
            ),
            mock.patch(
                "utils.object_management.signals.Group.objects.get_or_create",
                return_value=(moderators_group, False),
            ) as group_get_or_create,
            mock.patch(
                "utils.object_management.signals.ContentType.objects.get_for_model",
                return_value=mock.Mock(),
            ),
            mock.patch(
                "utils.object_management.signals.Permission.objects.get_or_create",
                side_effect=[Exception("boom"), (permission, False)],
            ) as permission_get_or_create,
        ):
            signals.ensure_moderation_permissions(sender=None, using="default")
            signals.ensure_moderation_permissions(sender=None, using="default")

        self.assertEqual(group_get_or_create.call_count, 2)
        self.assertEqual(permission_get_or_create.call_count, 2)
        moderators_group.permissions.add.assert_called_once_with(permission)
