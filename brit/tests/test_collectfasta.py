import hashlib
import json
import os
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.cache.backends.locmem import LocMemCache
from django.core.files.storage.memory import InMemoryStorage
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from brit.storages import StaticStorage


class CollectfastaProductionSettingsTests(SimpleTestCase):
    def run_production_script(self, script, settings_module="brit.settings.heroku"):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = settings_module
        environment["SECRET_KEY"] = "test-secret-key"
        environment["REDIS_URL"] = "redis://localhost:6379/0"
        environment["AWS_STORAGE_BUCKET_NAME"] = "brit-test-assets"
        environment["DATABASE_URL"] = (
            "postgres://postgres:postgres@localhost:5432/postgres"
        )
        environment.pop("AWS_ACCESS_KEY_ID", None)
        environment.pop("AWS_SECRET_ACCESS_KEY", None)
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

    def test_collectstatic_command_is_owned_by_collectfasta(self):
        completed = self.run_production_script(
            "import django; django.setup(); "
            "from django.core.management import get_commands; "
            "assert get_commands()['collectstatic'] == 'collectfasta'"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_collectfasta_is_installed_before_staticfiles(self):
        completed = self.run_production_script(
            """
import brit.settings.heroku as h
import brit.settings.settings as base

assert h.INSTALLED_APPS is not base.INSTALLED_APPS
assert h.INSTALLED_APPS[0] == "collectfasta"
assert h.INSTALLED_APPS.index("collectfasta") < h.INSTALLED_APPS.index(
    "django.contrib.staticfiles"
)
assert "collectfasta" not in base.INSTALLED_APPS
"""
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_collectfasta_uses_manifest_memory_strategy_without_threads(self):
        completed = self.run_production_script(
            """
import brit.settings.heroku as h

assert h.COLLECTFASTA_STRATEGY == (
    "collectfasta.strategies.boto3.Boto3ManifestMemoryStrategy"
)
assert h.COLLECTFASTA_CACHE == "collectfasta"
assert h.COLLECTFASTA_THREADS == 0
"""
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_collectfasta_cache_alias_is_dedicated_and_namespaced(self):
        completed = self.run_production_script(
            """
import brit.settings.heroku as h
import brit.settings.settings as base

alias = h.CACHES["collectfasta"]
assert h.CACHES is not base.CACHES
assert alias["BACKEND"] == "django_redis.cache.RedisCache"
assert alias["LOCATION"] == "redis://localhost:6379/0"
assert alias["TIMEOUT"] == 2592000
assert alias["KEY_PREFIX"] == "collectfasta:brit-test-assets:static"
assert alias["OPTIONS"]["CLIENT_CLASS"] == "django_redis.client.DefaultClient"
assert alias["OPTIONS"]["COMPRESSOR"] == (
    "django_redis.compressors.zlib.ZlibCompressor"
)
assert alias["OPTIONS"]["IGNORE_EXCEPTIONS"] is True
assert alias["OPTIONS"]["CONNECTION_POOL_KWARGS"] == {}
assert alias["OPTIONS"]["MAX_ENTRIES"] == 10000
assert "collectfasta" not in base.CACHES
assert "MAX_ENTRIES" not in base.CACHES["default"]["OPTIONS"]
"""
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_collectstatic_stays_stock_in_testrunner(self):
        completed = self.run_production_script(
            "import brit.settings.testrunner as t; "
            "import brit.settings.settings as base; "
            "assert 'collectfasta' not in t.INSTALLED_APPS; "
            "assert 'collectfasta' not in base.INSTALLED_APPS; "
            "assert 'collectfasta' not in t.CACHES; "
            "import django; django.setup(); "
            "from django.core.management import get_commands; "
            "assert get_commands()['collectstatic'] == 'django.contrib.staticfiles'",
            settings_module="brit.settings.testrunner",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class CollectfastaManifestUploadTests(SimpleTestCase):
    def setUp(self):
        self.fixture_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.fixture_dir.cleanup)
        fixture = Path(self.fixture_dir.name)
        (fixture / "css").mkdir()
        (fixture / "img").mkdir()
        self.css_path = fixture / "css" / "app.css"
        self.css_path.write_text("a{background:url(../img/logo.svg)}")
        (fixture / "img" / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        )
        self.remote = InMemoryStorage()
        self.remote.get_available_name = lambda name, max_length=None: name
        self.saved_names = []
        self.storage = self._patched_static_storage()
        self.collectfasta_cache = LocMemCache(
            f"collectfasta-test-{self._testMethodName}", {}
        )

    def _patched_static_storage(self):
        storage = StaticStorage(
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket_name="brit-test-assets",
            custom_domain="brit-test-assets.invalid",
            location="static",
            manifest_storage=InMemoryStorage(),
        )
        remote = self.remote
        saved_names = self.saved_names

        def save(name, content):
            saved_names.append(name)
            return remote._save(name, content)

        storage._save = save
        storage._open = remote._open
        storage.exists = remote.exists
        storage.delete = remote.delete
        storage.get_modified_time = remote.get_modified_time
        storage.get_available_name = remote.get_available_name
        return storage

    def _remote_file_hash(self, prefixed_path):
        try:
            with self.remote._open(prefixed_path) as remote_file:
                return hashlib.md5(remote_file.read()).hexdigest()
        except FileNotFoundError:
            return None

    def _run_collectstatic(self):
        from collectfasta import settings as collectfasta_settings
        from collectfasta.management.commands.collectstatic import Command
        from collectfasta.strategies import base as strategy_base
        from collectfasta.strategies.boto3 import Boto3Strategy

        with (
            override_settings(
                COLLECTFASTA_STRATEGY=(
                    "collectfasta.strategies.boto3.Boto3ManifestMemoryStrategy"
                ),
                STATICFILES_FINDERS=[
                    "django.contrib.staticfiles.finders.FileSystemFinder"
                ],
                STATICFILES_DIRS=[self.fixture_dir.name],
            ),
            mock.patch.object(
                Boto3Strategy,
                "wrapped_storage",
                lambda strategy, remote_storage: remote_storage,
            ),
            mock.patch.object(
                Boto3Strategy, "get_remote_file_hash", self._remote_file_hash
            ),
            mock.patch.object(strategy_base, "cache", self.collectfasta_cache),
            mock.patch.object(collectfasta_settings, "enabled", True),
            mock.patch.object(collectfasta_settings, "threads", 0),
        ):
            command = Command()
            command.storage = self.storage
            call_command(
                command,
                interactive=False,
                verbosity=0,
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def _remote_manifest(self):
        with self.remote._open("staticfiles.json") as manifest_file:
            return json.loads(manifest_file.read())

    def test_collectstatic_uploads_hashed_assets_and_manifest(self):
        self._run_collectstatic()

        manifest = self._remote_manifest()
        self.assertEqual(sorted(manifest["paths"]), ["css/app.css", "img/logo.svg"])
        hashed_css = manifest["paths"]["css/app.css"]
        hashed_logo = manifest["paths"]["img/logo.svg"]
        self.assertRegex(hashed_css, r"^css/app\.[0-9a-f]+\.css$")
        self.assertRegex(hashed_logo, r"^img/logo\.[0-9a-f]+\.svg$")
        for name in (
            "css/app.css",
            "img/logo.svg",
            hashed_css,
            hashed_logo,
            "staticfiles.json",
        ):
            self.assertTrue(self.remote.exists(name), name)
        with self.remote._open(hashed_css) as css_file:
            self.assertIn(hashed_logo.encode(), css_file.read())

    def test_second_run_skips_unchanged_remote_files(self):
        self._run_collectstatic()
        self.saved_names.clear()

        self._run_collectstatic()

        self.assertEqual(self.saved_names, [])

    def test_cleared_checksum_cache_still_skips_identical_remote_content(self):
        self._run_collectstatic()
        self.collectfasta_cache.clear()
        self.saved_names.clear()

        self._run_collectstatic()

        self.assertEqual(self.saved_names, [])

    def test_same_length_content_change_rewrites_manifest_in_place(self):
        self._run_collectstatic()
        old_hashed_css = self._remote_manifest()["paths"]["css/app.css"]
        self.saved_names.clear()
        self.css_path.write_text("b{background:url(../img/logo.svg)}")

        self._run_collectstatic()

        manifest = self._remote_manifest()
        new_hashed_css = manifest["paths"]["css/app.css"]
        self.assertNotEqual(old_hashed_css, new_hashed_css)
        self.assertCountEqual(
            self.saved_names, ["css/app.css", new_hashed_css, "staticfiles.json"]
        )
        self.assertTrue(self.remote.exists(new_hashed_css))
        self.assertTrue(self.remote.exists(old_hashed_css))

    def test_upload_error_propagates_instead_of_being_swallowed(self):
        def failing_save(name, content):
            raise OSError("upload failed")

        self.storage._save = failing_save

        with self.assertRaises(OSError):
            self._run_collectstatic()


class S3ManifestStaticStorageWrapperTests(SimpleTestCase):
    def test_manifest_name_is_reused_when_file_overwrite_is_disabled(self):
        from collectfasta.strategies.boto3 import S3ManifestStaticStorageWrapper

        wrapper = object.__new__(S3ManifestStaticStorageWrapper)
        wrapper.manifest_name = "staticfiles.json"
        wrapper.file_overwrite = False
        wrapper.exists = mock.Mock(return_value=True)

        self.assertEqual(
            wrapper.get_available_name("staticfiles.json"), "staticfiles.json"
        )
