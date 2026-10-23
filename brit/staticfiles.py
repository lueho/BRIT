import json
from urllib.parse import urlparse

from collectfasta.strategies.boto3 import (
    Boto3ManifestMemoryStrategy,
    Boto3WithoutPrefixStrategy,
    S3ManifestStaticStorageWrapper,
)
from django.core.files.base import ContentFile
from django.core.management.base import CommandError


class AtomicS3ManifestStorage(S3ManifestStaticStorageWrapper):
    def delete(self, name):
        pass


class AtomicBoto3Strategy(Boto3WithoutPrefixStrategy):
    def wrapped_storage(self, remote_storage):
        storage = AtomicS3ManifestStorage(original=remote_storage)
        storage.file_overwrite = True
        return storage

    def should_copy_file(self, path, prefixed_path, local_storage):
        if prefixed_path == self.remote_storage.manifest_name:
            with local_storage.open(path) as local_file:
                local_content = local_file.read()
            try:
                with self.remote_storage.open(prefixed_path) as remote_file:
                    remote_content = remote_file.read()
            except FileNotFoundError:
                return True
            return local_content != remote_content
        return super().should_copy_file(path, prefixed_path, local_storage)


class SafeManifestMemoryStrategy(Boto3ManifestMemoryStrategy):
    second_strategy = AtomicBoto3Strategy


def _is_safe_relative_path(value):
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return False
    if value.startswith("/") or "\\" in value:
        return False
    return ".." not in value.split("/")


def load_static_manifest(content, storage):
    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        manifest = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise CommandError(f"Static files manifest is not valid JSON: {e}") from e
    if not isinstance(manifest, dict):
        raise CommandError("Static files manifest is not a JSON object.")
    if manifest.get("version") != storage.manifest_version:
        raise CommandError(
            f"Static files manifest has version {manifest.get('version')!r}, "
            f"expected {storage.manifest_version!r}."
        )
    paths = manifest.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise CommandError("Static files manifest has no file paths.")
    for source, destination in paths.items():
        if not (_is_safe_relative_path(source) and _is_safe_relative_path(destination)):
            raise CommandError(
                f"Static files manifest contains an unsafe path: {source!r} -> {destination!r}"
            )
    expected_hash = storage.file_hash(
        None, ContentFile(json.dumps(sorted(paths.items())).encode())
    )
    if manifest.get("hash") != expected_hash:
        raise CommandError("Static files manifest hash does not match its file paths.")
    return manifest


def check_manifest_files(storage, manifest):
    location = getattr(storage, "location", "") or ""
    if not _is_safe_relative_path(location.rstrip("/")):
        raise CommandError(
            f"Storage location {location!r} is not a safe relative prefix."
        )
    prefix = location.rstrip("/") + "/"
    paginator = storage.bucket.meta.client.get_paginator("list_objects_v2")
    remote_names = set()
    for page in paginator.paginate(Bucket=storage.bucket_name, Prefix=prefix):
        for entry in page.get("Contents", []):
            key = entry["Key"]
            if not key.startswith(prefix):
                raise CommandError(
                    f"Storage listing returned an object outside {prefix!r}: {key!r}"
                )
            remote_names.add(key[len(prefix) :])
    referenced = set(manifest["paths"]) | set(manifest["paths"].values())
    missing = sorted(referenced - remote_names)
    if missing:
        preview = ", ".join(missing[:5])
        raise CommandError(
            f"{len(missing)} manifest file(s) are missing from remote "
            f"storage: {preview}"
        )
    return len(manifest["paths"])
