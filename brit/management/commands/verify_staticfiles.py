from pathlib import Path

from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError

from brit.staticfiles import check_manifest_files, load_static_manifest


class Command(BaseCommand):
    help = "Verify the deployed static files manifest matches the release receipt."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            required=True,
            help="Manifest receipt written by collectstatic_safe --manifest-output.",
        )

    def handle(self, *args, **options):
        storage = storages["staticfiles"]
        try:
            receipt_bytes = Path(options["manifest"]).read_bytes()
        except OSError as e:
            raise CommandError(
                f"Cannot read manifest receipt {options['manifest']!r}: {e}"
            ) from e
        expected = load_static_manifest(receipt_bytes, storage)
        try:
            with storage.open(storage.manifest_name) as remote_manifest:
                remote_bytes = remote_manifest.read()
        except OSError as e:
            raise CommandError(f"Cannot read remote staticfiles.json: {e}") from e
        actual = load_static_manifest(remote_bytes, storage)
        if actual != expected:
            raise CommandError(
                "Deployed staticfiles.json does not match the release receipt."
            )
        count = check_manifest_files(storage, actual)
        self.stdout.write(f"Verified {count} static files.")
