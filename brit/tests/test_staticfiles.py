import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase
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


class StaticAssetReleaseTests(SimpleTestCase):
    def test_release_runs_migrations_then_collectstatic(self):
        manifest = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "heroku.yml").read_text()
        )
        commands = manifest["release"]["command"]
        self.assertEqual(len(commands), 1)

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "python"
            executable.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$RELEASE_TEST_LOG"\n'
            )
            executable.chmod(0o755)
            log = Path(directory) / "calls.log"
            result = subprocess.run(
                commands[0],
                shell=True,
                env={
                    **os.environ,
                    "PATH": f"{directory}:{os.environ['PATH']}",
                    "RELEASE_TEST_LOG": str(log),
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text().splitlines(),
                ["manage.py migrate --noinput", "manage.py collectstatic --noinput"],
            )
