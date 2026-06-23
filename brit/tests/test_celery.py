import subprocess
import sys
from importlib import import_module

from django.test import SimpleTestCase


class CelerySettingsTests(SimpleTestCase):
    def test_celery_defaults_to_local_settings_without_env_override(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "os.environ.pop('DJANGO_SETTINGS_MODULE', None); "
                    "import brit.celery; "
                    "print(os.environ['DJANGO_SETTINGS_MODULE'])"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "brit.settings.local")

    def test_local_settings_use_local_file_export_storage(self):
        local_settings = import_module("brit.settings.local")

        self.assertIs(local_settings.FILE_EXPORT_USE_LOCAL_STORAGE, True)
        self.assertEqual(local_settings.MEDIA_URL, "/media/")
