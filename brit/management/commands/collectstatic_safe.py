from pathlib import Path

from collectfasta import settings as collectfasta_settings
from collectfasta.management.commands.collectstatic import (
    Command as CollectfastaCommand,
)
from django.core.management.base import CommandError

from brit.staticfiles import (
    AtomicBoto3Strategy,
    SafeManifestMemoryStrategy,
    check_manifest_files,
    load_static_manifest,
)


class Command(CollectfastaCommand):
    help = "Collect static files and publish the manifest atomically, last."

    def __init__(self, *args, **kwargs):
        self.manifest_output = None
        self._pending_manifest_args = None
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--manifest-output",
            required=True,
            help="Local path for the manifest receipt written before publication.",
        )

    @staticmethod
    def _load_strategy():
        return SafeManifestMemoryStrategy

    def set_options(self, **options):
        self.manifest_output = options["manifest_output"]
        if options["clear"]:
            raise CommandError("collectstatic_safe does not support --clear.")
        if options["disable_collectfasta"] or not self.collectfasta_enabled:
            raise CommandError("collectstatic_safe requires Collectfasta enabled.")
        if not options["post_process"]:
            raise CommandError("collectstatic_safe requires manifest post-processing.")
        if collectfasta_settings.threads:
            raise CommandError(
                "collectstatic_safe requires synchronous uploads "
                "(COLLECTFASTA_THREADS=0)."
            )
        self._pending_manifest_args = None
        super().set_options(**options)

    def maybe_copy_file(self, args):
        if isinstance(self.strategy, AtomicBoto3Strategy):
            target = self.strategy.copy_args_hook(args)[1]
            if target == self.storage.manifest_name:
                self._pending_manifest_args = args
                return
        return super().maybe_copy_file(args)

    def second_pass(self, stats):
        self._pending_manifest_args = None
        result = super().second_pass(stats)
        if self.dry_run:
            return result
        if self._pending_manifest_args is None:
            raise CommandError("collectstatic_safe did not see a manifest task.")
        args = self._pending_manifest_args
        path, prefixed_path, source_storage = self.strategy.copy_args_hook(args)
        with source_storage.open(path) as source_file:
            manifest_bytes = source_file.read()
        manifest = load_static_manifest(manifest_bytes, self.storage)
        check_manifest_files(self.storage, manifest)
        Path(self.manifest_output).write_bytes(manifest_bytes)
        super().maybe_copy_file(args)
        result["modified"] = self.copied_files + self.symlinked_files
        return result
