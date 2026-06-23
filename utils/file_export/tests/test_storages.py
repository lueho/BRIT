from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings

from utils.file_export.storages import write_file_for_download


class BytesRenderer:
    def render(self, file, data):
        file.write(data)


class FileExportStorageTests(SimpleTestCase):
    def test_write_file_for_download_uses_local_storage_when_configured(self):
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                url = write_file_for_download(
                    "export.csv",
                    b"header\nvalue\n",
                    BytesRenderer,
                )

            self.assertEqual(url, "/media/tmp/export.csv")
            self.assertEqual(
                Path(tmpdir, "tmp", "export.csv").read_bytes(),
                b"header\nvalue\n",
            )
