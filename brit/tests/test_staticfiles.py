import json
import tempfile

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from storages.backends.s3boto3 import S3ManifestStaticStorage

from brit.storages import StaticStorage


class FakeManifestStorage:
    def __init__(self):
        self.deleted_names = []
        self.saved_files = []

    def exists(self, name):
        return True

    def delete(self, name):
        self.deleted_names.append(name)

    def _save(self, name, content):
        self.saved_files.append((name, content.read()))
        return name


class StaticStorageCacheBustingTests(SimpleTestCase):
    def test_static_storage_uses_manifest_hashed_filenames(self):
        self.assertTrue(issubclass(StaticStorage, S3ManifestStaticStorage))

    def test_static_storage_skips_unchanged_files(self):
        self.assertFalse(StaticStorage.file_overwrite)

    def test_static_storage_still_overwrites_manifest(self):
        storage = object.__new__(StaticStorage)
        storage.hashed_files = {"css/app.css": "css/app.123456789abc.css"}
        storage.manifest_name = "staticfiles.json"
        storage.manifest_version = "1.1"
        storage.manifest_storage = FakeManifestStorage()

        storage.save_manifest()

        self.assertEqual(storage.manifest_storage.deleted_names, ["staticfiles.json"])
        saved_name, saved_content = storage.manifest_storage.saved_files[0]
        self.assertEqual(saved_name, "staticfiles.json")
        self.assertEqual(
            json.loads(saved_content),
            {
                "paths": {"css/app.css": "css/app.123456789abc.css"},
                "version": "1.1",
                "hash": storage.manifest_hash,
            },
        )


class CollectstaticManifestTests(SimpleTestCase):
    """Smoke test for the production collectstatic path.

    Production uses S3ManifestStaticStorage, whose manifest post-processing
    resolves and hashes every url(...) reference in shipped CSS. A vendored
    stylesheet that references files we did not ship (e.g. a missing font
    format) fails at release time. Running collectstatic with the local
    ManifestStaticFilesStorage exercises the same code path without S3.
    """

    def test_collectstatic_resolves_all_css_url_references(self):
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
            },
        }
        with tempfile.TemporaryDirectory() as static_root:
            with override_settings(STATIC_ROOT=static_root, STORAGES=storages):
                call_command("collectstatic", "--no-input", verbosity=0)
