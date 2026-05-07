from django.test import SimpleTestCase
from storages.backends.s3boto3 import S3ManifestStaticStorage

from brit.storages import StaticStorage


class StaticStorageCacheBustingTests(SimpleTestCase):
    def test_static_storage_uses_manifest_hashed_filenames(self):
        self.assertTrue(issubclass(StaticStorage, S3ManifestStaticStorage))

    def test_static_storage_skips_unchanged_files(self):
        self.assertFalse(StaticStorage.file_overwrite)
