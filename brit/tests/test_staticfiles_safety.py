import hashlib
import json
import os
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from collectfasta.strategies.boto3 import S3ManifestStaticStorageWrapper
from django.core.cache.backends.locmem import LocMemCache
from django.core.files.base import ContentFile
from django.core.files.storage.memory import InMemoryStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from brit.staticfiles import (
    AtomicBoto3Strategy,
    AtomicS3ManifestStorage,
    check_manifest_files,
    load_static_manifest,
)
from brit.storages import StaticStorage


class AtomicManifestStorageTests(SimpleTestCase):
    def _original(self):
        return StaticStorage(
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket_name="brit-test-assets",
            custom_domain="brit-test-assets.invalid",
            location="static",
            manifest_storage=InMemoryStorage(),
        )

    def _wrapper(self):
        strategy = AtomicBoto3Strategy.__new__(AtomicBoto3Strategy)
        return strategy.wrapped_storage(self._original())

    def test_wrapped_storage_is_atomic_and_overwrites(self):
        wrapper = self._wrapper()
        self.assertIsInstance(wrapper, AtomicS3ManifestStorage)
        self.assertTrue(wrapper.file_overwrite)
        self.assertEqual(wrapper.manifest_name, "staticfiles.json")

    def test_delete_never_reaches_s3(self):
        wrapper = self._wrapper()
        with mock.patch.object(
            S3ManifestStaticStorageWrapper, "delete"
        ) as parent_delete:
            wrapper.delete("css/app.css")
            wrapper.delete("staticfiles.json")
        parent_delete.assert_not_called()

    def test_save_preserves_requested_names(self):
        wrapper = self._wrapper()
        wrapper.exists = lambda name: True
        saved = []
        wrapper._save = lambda name, content: saved.append(name) or name

        self.assertEqual(wrapper.save("css/app.css", ContentFile(b"x")), "css/app.css")
        self.assertEqual(
            wrapper.save("staticfiles.json", ContentFile(b"{}")),
            "staticfiles.json",
        )
        self.assertEqual(saved, ["css/app.css", "staticfiles.json"])


class StaticfilesSafetyTestBase(SimpleTestCase):
    def setUp(self):
        self.fixture_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.fixture_dir.cleanup)
        self.out_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.out_dir.cleanup)
        fixture = Path(self.fixture_dir.name)
        (fixture / "css").mkdir()
        (fixture / "img").mkdir()
        self.css_path = fixture / "css" / "app.css"
        self.css_path.write_text("a{background:url(../img/logo.svg)}")
        (fixture / "img" / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        )
        (fixture / "zzz.js").write_text("console.log('zzz')")
        self.receipt_path = str(Path(self.out_dir.name) / "receipt.json")
        self.remote = InMemoryStorage()
        self.remote.get_available_name = lambda name, max_length=None: name
        self.saved_names = []
        self.storage = self._fake_atomic_storage()
        self.collectfasta_cache = LocMemCache(
            f"collectfasta-safety-{self._testMethodName}", {}
        )

    def _fake_atomic_storage(self):
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
        storage.delete = lambda name: None
        storage.get_modified_time = remote.get_modified_time
        storage.get_available_name = remote.get_available_name
        return storage

    def _remote_names(self):
        names = []

        def walk(prefix):
            dirs, files = self.remote.listdir(prefix)
            names.extend(f"{prefix}/{f}" if prefix else f for f in files)
            for directory in dirs:
                walk(f"{prefix}/{directory}" if prefix else directory)

        walk("")
        return sorted(names)

    def _remote_bytes(self, name):
        with self.remote._open(name) as remote_file:
            return remote_file.read()

    def _remote_file_hash(self, prefixed_path):
        try:
            with self.remote._open(prefixed_path) as remote_file:
                return hashlib.md5(remote_file.read()).hexdigest()
        except FileNotFoundError:
            return None

    def _install_paginator(self, page_size=2):
        def paginate(**kwargs):
            keys = [
                {"Key": f"{self.storage.location}/{name}"}
                for name in self._remote_names()
            ]
            return [
                {"Contents": keys[i : i + page_size]}
                for i in range(0, len(keys), page_size)
            ]

        paginator = mock.Mock()
        paginator.paginate = mock.Mock(side_effect=lambda **kwargs: paginate())
        client = mock.Mock()
        client.get_paginator = mock.Mock(return_value=paginator)
        self.storage._bucket = SimpleNamespace(meta=SimpleNamespace(client=client))
        return client, paginator

    def _run_safe(self, enabled=True, threads=0, **kwargs):
        from collectfasta import settings as collectfasta_settings
        from collectfasta.strategies import base as strategy_base
        from collectfasta.strategies.boto3 import Boto3Strategy

        from brit.management.commands.collectstatic_safe import Command

        options = {
            "interactive": False,
            "verbosity": 0,
            "manifest_output": self.receipt_path,
            "stdout": StringIO(),
            "stderr": StringIO(),
        }
        options.update(kwargs)
        with (
            override_settings(
                STATICFILES_FINDERS=[
                    "django.contrib.staticfiles.finders.FileSystemFinder"
                ],
                STATICFILES_DIRS=[self.fixture_dir.name],
            ),
            mock.patch.object(
                AtomicBoto3Strategy,
                "wrapped_storage",
                lambda strategy, remote_storage: self.storage,
            ),
            mock.patch.object(
                Boto3Strategy, "get_remote_file_hash", self._remote_file_hash
            ),
            mock.patch.object(strategy_base, "cache", self.collectfasta_cache),
            mock.patch.object(collectfasta_settings, "enabled", enabled),
            mock.patch.object(collectfasta_settings, "threads", threads),
        ):
            command = Command()
            command.storage = self.storage
            call_command(command, **options)

    def _run_verify(self, **kwargs):
        import brit.management.commands.verify_staticfiles as verify_module

        command = verify_module.Command()
        options = {
            "manifest": self.receipt_path,
            "stdout": StringIO(),
            "stderr": StringIO(),
        }
        options.update(kwargs)
        with mock.patch.object(
            verify_module, "storages", {"staticfiles": self.storage}
        ):
            return call_command(command, **options)


class CollectstaticSafeTests(StaticfilesSafetyTestBase):
    def test_initial_publication_writes_manifest_last_and_receipt(self):
        client, paginator = self._install_paginator()

        self._run_safe()

        self.assertEqual(self.saved_names[-1], "staticfiles.json")
        self.assertLess(
            self.saved_names.index("zzz.js"),
            self.saved_names.index("staticfiles.json"),
        )
        manifest = json.loads(self._remote_bytes("staticfiles.json"))
        self.assertEqual(
            sorted(manifest["paths"]), ["css/app.css", "img/logo.svg", "zzz.js"]
        )
        self.assertEqual(
            Path(self.receipt_path).read_bytes(),
            self._remote_bytes("staticfiles.json"),
        )
        self._run_verify()
        client.get_paginator.assert_called_with("list_objects_v2")
        paginator.paginate.assert_called_with(
            Bucket="brit-test-assets", Prefix="static/"
        )

    def test_warm_run_skips_uploads_but_writes_receipt(self):
        self._install_paginator()
        self._run_safe()
        self.saved_names.clear()
        self._install_paginator()

        self._run_safe()

        self.assertEqual(self.saved_names, [])
        self.assertTrue(Path(self.receipt_path).exists())
        self.assertEqual(
            Path(self.receipt_path).read_bytes(),
            self._remote_bytes("staticfiles.json"),
        )

    def test_same_length_change_rewrites_manifest_in_place(self):
        self._install_paginator()
        self._run_safe()
        old_manifest = json.loads(self._remote_bytes("staticfiles.json"))
        old_hashed_css = old_manifest["paths"]["css/app.css"]
        self.saved_names.clear()
        self.css_path.write_text("b{background:url(../img/logo.svg)}")
        self._install_paginator()

        self._run_safe()

        new_manifest = json.loads(self._remote_bytes("staticfiles.json"))
        new_hashed_css = new_manifest["paths"]["css/app.css"]
        self.assertNotEqual(old_hashed_css, new_hashed_css)
        self.assertCountEqual(
            self.saved_names, ["css/app.css", new_hashed_css, "staticfiles.json"]
        )
        self.assertTrue(self.remote.exists(new_hashed_css))
        self.assertTrue(self.remote.exists(old_hashed_css))

    def test_failed_asset_upload_keeps_old_manifest(self):
        self._install_paginator()
        self._run_safe()
        old_manifest = self._remote_bytes("staticfiles.json")
        (Path(self.fixture_dir.name) / "zz-fail.js").write_text("console.log('new')")
        self._install_paginator()

        real_save = self.storage._save

        def failing_save(name, content):
            if name == "zz-fail.js":
                raise OSError("upload failed")
            return real_save(name, content)

        self.storage._save = failing_save

        self.saved_names.clear()
        with self.assertRaises(OSError):
            self._run_safe()

        self.assertEqual(self._remote_bytes("staticfiles.json"), old_manifest)
        self.assertNotIn("staticfiles.json", self.saved_names)

    def test_failed_manifest_write_keeps_old_manifest(self):
        self._install_paginator()
        self._run_safe()
        old_manifest = self._remote_bytes("staticfiles.json")
        self.css_path.write_text("b{background:url(../img/logo.svg)}")
        self._install_paginator()

        real_save = self.storage._save

        def failing_save(name, content):
            if name == "staticfiles.json":
                raise OSError("manifest upload failed")
            return real_save(name, content)

        self.storage._save = failing_save

        with self.assertRaises(OSError):
            self._run_safe()

        self.assertEqual(self._remote_bytes("staticfiles.json"), old_manifest)

    def test_missing_remote_object_fails_before_manifest_publication(self):
        self._install_paginator()
        self._run_safe()
        old_manifest = self._remote_bytes("staticfiles.json")
        hashed_css = json.loads(old_manifest)["paths"]["css/app.css"]
        self.remote.delete(hashed_css)
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_safe()

        self.assertEqual(self._remote_bytes("staticfiles.json"), old_manifest)

    def test_receipt_write_failure_keeps_old_manifest(self):
        self._install_paginator()
        self._run_safe()
        old_manifest = self._remote_bytes("staticfiles.json")
        self.css_path.write_text("b{background:url(../img/logo.svg)}")
        self.saved_names.clear()
        self.receipt_path = "/nonexistent-dir/receipt.json"
        self._install_paginator()

        with self.assertRaises(OSError):
            self._run_safe()

        self.assertEqual(self._remote_bytes("staticfiles.json"), old_manifest)
        self.assertNotIn("staticfiles.json", self.saved_names)


class CollectstaticSafeCliTests(StaticfilesSafetyTestBase):
    def test_rejects_clear(self):
        with self.assertRaises(CommandError):
            self._run_safe(clear=True)
        self.assertEqual(self.remote.listdir(""), ([], []))

    def test_rejects_no_post_process(self):
        with self.assertRaises(CommandError):
            self._run_safe(post_process=False)
        self.assertEqual(self.remote.listdir(""), ([], []))

    def test_rejects_disable_collectfasta_flag(self):
        with self.assertRaises(CommandError):
            self._run_safe(disable_collectfasta=True)
        self.assertEqual(self.remote.listdir(""), ([], []))

    def test_rejects_disabled_collectfasta(self):
        with self.assertRaises(CommandError):
            self._run_safe(enabled=False)
        self.assertEqual(self.remote.listdir(""), ([], []))

    def test_rejects_threaded_uploads(self):
        with self.assertRaises(CommandError):
            self._run_safe(threads=8)
        self.assertEqual(self.remote.listdir(""), ([], []))

    def test_dry_run_writes_neither_remote_nor_receipt(self):
        self._run_safe(dry_run=True)

        self.assertEqual(self.saved_names, [])
        self.assertEqual(self.remote.listdir(""), ([], []))
        self.assertFalse(Path(self.receipt_path).exists())


class VerifyStaticfilesTests(StaticfilesSafetyTestBase):
    def _seed(self):
        self._install_paginator()
        self._run_safe()
        return json.loads(self._remote_bytes("staticfiles.json"))

    def test_verifies_published_manifest(self):
        self._seed()
        self.storage.hashed_files = {"stale.css": "stale.deadbeef.css"}
        self._install_paginator()

        self._run_verify()

    def test_rejects_missing_remote_manifest(self):
        self._seed()
        self.remote.delete("staticfiles.json")
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_corrupt_remote_manifest(self):
        self._seed()
        self.remote._save("staticfiles.json", ContentFile(b"{not json"))
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_empty_manifest_paths(self):
        self._seed()
        self.remote._save(
            "staticfiles.json",
            ContentFile(
                json.dumps({"paths": {}, "version": "1.1", "hash": "x"}).encode()
            ),
        )
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_wrong_manifest_hash(self):
        self._seed()
        self.remote._save(
            "staticfiles.json",
            ContentFile(
                json.dumps(
                    {
                        "paths": {"a.css": "a.1.css"},
                        "version": "1.1",
                        "hash": "deadbeef",
                    }
                ).encode()
            ),
        )
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_missing_receipt(self):
        self._seed()

        with self.assertRaises(CommandError):
            self._run_verify(manifest="/nonexistent/receipt.json")

    def test_rejects_malformed_receipt(self):
        self._seed()
        Path(self.receipt_path).write_bytes(b"not json")

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_stale_remote_manifest(self):
        self._seed()
        stale_manifest = self._remote_bytes("staticfiles.json")
        self.css_path.write_text("b{background:url(../img/logo.svg)}")
        self._install_paginator()
        self._run_safe()
        self.remote._save("staticfiles.json", ContentFile(stale_manifest))
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()

    def test_rejects_missing_referenced_object(self):
        manifest = self._seed()
        self.remote.delete(manifest["paths"]["css/app.css"])
        self._install_paginator()

        with self.assertRaises(CommandError):
            self._run_verify()


class LoadStaticManifestTests(StaticfilesSafetyTestBase):
    def _manifest_bytes(self, paths=None, version=None, manifest_hash=None):
        paths = {"a.css": "a.1.css"} if paths is None else paths
        payload = {
            "paths": paths,
            "version": (self.storage.manifest_version if version is None else version),
            "hash": (
                self.storage.file_hash(
                    None,
                    ContentFile(json.dumps(sorted(paths.items())).encode()),
                )
                if manifest_hash is None
                else manifest_hash
            ),
        }
        return json.dumps(payload).encode()

    def test_accepts_valid_manifest(self):
        manifest = load_static_manifest(self._manifest_bytes(), self.storage)
        self.assertEqual(manifest["paths"], {"a.css": "a.1.css"})
        self.assertEqual(manifest["version"], self.storage.manifest_version)

    def test_rejects_invalid_json(self):
        with self.assertRaises(CommandError):
            load_static_manifest(b"{oops", self.storage)

    def test_rejects_invalid_utf8(self):
        with self.assertRaises(CommandError):
            load_static_manifest(b'\xff\xfe{"paths": {}}', self.storage)

    def test_rejects_non_object_manifest(self):
        with self.assertRaises(CommandError):
            load_static_manifest(b'["a.css"]', self.storage)

    def test_rejects_wrong_version(self):
        with self.assertRaises(CommandError):
            load_static_manifest(self._manifest_bytes(version="9.9"), self.storage)

    def test_rejects_empty_paths(self):
        with self.assertRaises(CommandError):
            load_static_manifest(self._manifest_bytes(paths={}), self.storage)

    def test_rejects_wrong_hash(self):
        with self.assertRaises(CommandError):
            load_static_manifest(
                self._manifest_bytes(manifest_hash="deadbeef"), self.storage
            )

    def test_rejects_unsafe_paths(self):
        unsafe = [
            "../escape.css",
            "/absolute.css",
            "back\\slash.css",
            "https://host/x.css",
            "//host/x.css",
            "scheme:thing.css",
            "",
        ]
        for bad in unsafe:
            for paths in ({bad: "a.1.css"}, {"a.css": bad}):
                with self.assertRaises(CommandError, msg=paths):
                    load_static_manifest(
                        self._manifest_bytes(paths=paths), self.storage
                    )

    def test_accepts_slash_paths(self):
        manifest = load_static_manifest(
            self._manifest_bytes(paths={"css/app.css": "css/app.1234abcd.css"}),
            self.storage,
        )
        self.assertIn("css/app.css", manifest["paths"])


class CheckManifestFilesTests(StaticfilesSafetyTestBase):
    def _manifest(self):
        return {"paths": {"a.css": "a.1.css", "b.css": "b.2.css"}}

    def test_reads_all_pages(self):
        for name in ("a.1.css", "b.2.css", "extra.css"):
            self.remote._save(name, ContentFile(b"x"))
        client, paginator = self._install_paginator(page_size=1)

        self.assertEqual(check_manifest_files(self.storage, self._manifest()), 2)
        client.get_paginator.assert_called_once_with("list_objects_v2")
        paginator.paginate.assert_called_once_with(
            Bucket="brit-test-assets", Prefix="static/"
        )

    def test_rejects_object_keys_outside_location_prefix(self):
        paginator = mock.Mock()
        paginator.paginate = mock.Mock(
            return_value=[{"Contents": [{"Key": "other/a.1.css"}]}]
        )
        client = mock.Mock()
        client.get_paginator = mock.Mock(return_value=paginator)
        self.storage._bucket = SimpleNamespace(meta=SimpleNamespace(client=client))

        with self.assertRaises(CommandError):
            check_manifest_files(self.storage, self._manifest())

    def test_reports_missing_objects(self):
        self.remote._save("a.1.css", ContentFile(b"x"))
        self._install_paginator()

        with self.assertRaises(CommandError):
            check_manifest_files(self.storage, self._manifest())

    def test_rejects_unsafe_location(self):
        self.storage.location = ".."
        with self.assertRaises(CommandError):
            check_manifest_files(self.storage, self._manifest())

    def test_rejects_empty_location(self):
        self.storage.location = ""
        with self.assertRaises(CommandError):
            check_manifest_files(self.storage, self._manifest())


class GuardedCommandDiscoveryTests(SimpleTestCase):
    def _run_script(self, script, settings_module):
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

    def test_production_discovers_safe_commands(self):
        completed = self._run_script(
            "import django; django.setup(); "
            "from django.core.management import get_commands; "
            "commands = get_commands(); "
            "assert commands['collectstatic_safe'] == 'brit'; "
            "assert commands['verify_staticfiles'] == 'brit'; "
            "assert commands['collectstatic'] == 'collectfasta'",
            "brit.settings.heroku",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_testrunner_discovers_safe_commands_with_stock_collectstatic(self):
        completed = self._run_script(
            "import django; django.setup(); "
            "from django.core.management import get_commands; "
            "commands = get_commands(); "
            "assert commands['collectstatic_safe'] == 'brit'; "
            "assert commands['verify_staticfiles'] == 'brit'; "
            "assert commands['collectstatic'] == 'django.contrib.staticfiles'",
            "brit.settings.testrunner",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
