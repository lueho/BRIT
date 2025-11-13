import os
from unittest import mock

from django.test import TestCase, override_settings

from utils.object_management import utils as obj_utils


class ObjectManagementInitialDataTests(TestCase):
    def test_missing_env_variables_raises_runtime_error(self):
        """ensure_initial_data should fail if no usernames are configured."""
        with override_settings(DEFAULT_OBJECT_OWNER_USERNAME=None):
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(RuntimeError):
                    obj_utils.ensure_initial_data()
