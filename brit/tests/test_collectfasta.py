import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.cache.backends.locmem import LocMemCache
from django.core.files.storage.memory import InMemoryStorage
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from brit.storages import StaticStorage
from brit.tests.probes import run_settings_probe

_PRODUCTION_SNAPSHOT_SCRIPT = """
import json

import brit.settings.heroku as h
import brit.settings.settings as base

alias = h.CACHES["collectfasta"]
snapshot = {
    "installed_apps": list(h.INSTALLED_APPS),
    "installed_apps_distinct": h.INSTALLED_APPS is not base.INSTALLED_APPS,
    "base_has_collectfasta_app": "collectfasta" in base.INSTALLED_APPS,
    "strategy": h.COLLECTFASTA_STRATEGY,
    "cache_name": h.COLLECTFASTA_CACHE,
    "threads": h.COLLECTFASTA_THREADS,
    "caches_distinct": h.CACHES is not base.CACHES,
    "base_has_collectfasta_cache": "collectfasta" in base.CACHES,
    "base_default_options_has_max_entries": (
        "MAX_ENTRIES" in base.CACHES["default"]["OPTIONS"]
    ),
    "collectfasta_alias": {
        "BACKEND": alias["BACKEND"],
        "LOCATION": alias["LOCATION"],
        "TIMEOUT": alias["TIMEOUT"],
        "KEY_PREFIX": alias["KEY_PREFIX"],
        "OPTIONS": alias["OPTIONS"],
    },
}

import django

django.setup()
from django.core.management import get_commands

snapshot["collectstatic_owner"] = get_commands()["collectstatic"]
print(json.dumps(snapshot))
"""


class CollectfastaProductionSettingsTests(SimpleTestCase):
    """All production probes share one subprocess snapshot from setUpClass."""

    snapshot = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        completed = cls.run_production_script(_PRODUCTION_SNAPSHOT_SCRIPT)
        if completed.returncode != 0:
            raise AssertionError(
                "production settings probe failed with exit code "
                f"{completed.returncode}:\n{completed.stderr}"
            )
        cls.snapshot = json.loads(completed.stdout)

    @classmethod
    def run_production_script(cls, script, settings_module="brit.settings.heroku"):
        return run_settings_probe(
            script,
            env={
                "DJANGO_SETTINGS_MODULE": settings_module,
                "SECRET_KEY": "test-secret-key",
                "REDIS_URL": "redis://localhost:6379/0",
                "AWS_STORAGE_BUCKET_NAME": "brit-test-assets",
                "DATABASE_URL": (
                    "postgres://postgres:postgres@localhost:5432/postgres"
                ),
                "AWS_ACCESS_KEY_ID": None,
                "AWS_SECRET_ACCESS_KEY": None,
            },
        )

    def test_collectstatic_command_is_owned_by_collectfasta(self):
        self.assertEqual(self.snapshot["collectstatic_owner"], "collectfasta")

    def test_collectfasta_is_installed_before_staticfiles(self):
        installed_apps = self.snapshot["installed_apps"]
        self.assertTrue(self.snapshot["installed_apps_distinct"])
        self.assertEqual(installed_apps[0], "collectfasta")
        self.assertLess(
            installed_apps.index("collectfasta"),
            installed_apps.index("django.contrib.staticfiles"),
        )
        self.assertFalse(self.snapshot["base_has_collectfasta_app"])

    def test_collectfasta_uses_manifest_memory_strategy_without_threads(self):
        self.assertEqual(
            self.snapshot["strategy"],
            "collectfasta.strategies.boto3.Boto3ManifestMemoryStrategy",
        )
        self.assertEqual(self.snapshot["cache_name"], "collectfasta")
        self.assertEqual(self.snapshot["threads"], 0)

    def test_collectfasta_cache_alias_is_dedicated_and_namespaced(self):
        self.assertTrue(self.snapshot["caches_distinct"])
        alias = self.snapshot["collectfasta_alias"]
        self.assertEqual(alias["BACKEND"], "django_redis.cache.RedisCache")
        self.assertEqual(alias["LOCATION"], "redis://localhost:6379/0")
        self.assertEqual(alias["TIMEOUT"], 2592000)
        self.assertEqual(alias["KEY_PREFIX"], "collectfasta:brit-test-assets:static")
        self.assertEqual(
            alias["OPTIONS"]["CLIENT_CLASS"], "django_redis.client.DefaultClient"
        )
        self.assertEqual(
            alias["OPTIONS"]["COMPRESSOR"],
            "django_redis.compressors.zlib.ZlibCompressor",
        )
        self.assertIs(alias["OPTIONS"]["IGNORE_EXCEPTIONS"], True)
        self.assertEqual(alias["OPTIONS"]["CONNECTION_POOL_KWARGS"], {})
        self.assertEqual(alias["OPTIONS"]["MAX_ENTRIES"], 10000)
        self.assertFalse(self.snapshot["base_has_collectfasta_cache"])
        self.assertFalse(self.snapshot["base_default_options_has_max_entries"])

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


class CollectfastaProductionProbeCountTests(SimpleTestCase):
    """The shared production snapshot must come from one subprocess probe."""

    def test_snapshot_probe_runs_one_subprocess(self):
        class ProbeHarness(CollectfastaProductionSettingsTests):
            pass

        self.addCleanup(ProbeHarness.doClassCleanups)
        original_snapshot = CollectfastaProductionSettingsTests.snapshot
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps({"probe": "sentinel"}),
            stderr="",
        )
        with mock.patch(
            "brit.tests.test_collectfasta.run_settings_probe",
            return_value=completed,
        ) as probe:
            ProbeHarness.setUpClass()

        probe.assert_called_once()
        self.assertEqual(ProbeHarness.snapshot, {"probe": "sentinel"})
        self.assertIs(CollectfastaProductionSettingsTests.snapshot, original_snapshot)
