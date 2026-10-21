"""
Bootstraps a BRIT database from scratch.

A fresh database normally only needs ``migrate`` followed by
``ensure_initial_data``: the schema-only replacement migrations for
``properties`` and ``materials`` contain no data operations, and the
required default rows are created by the app initializers. The original
migration files and the ``replaces`` metadata stay available so that
databases with fully applied legacy histories adopt the replacements
automatically. Databases with a partially applied legacy history cannot
use the replacements yet, so for them this command keeps the older staged
sequence that interleaves schema and data setup.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = (
        "Applies migrations and seeds initial data. Normally runs plain "
        "migrate followed by ensure_initial_data; falls back to the staged "
        "compatibility sequence for databases with a partially applied "
        "legacy properties/materials migration history. Safe to run "
        "repeatedly."
    )

    requires_system_checks = []

    STAGES = (
        ("migrate", (), {"interactive": False}),
        ("ensure_initial_data", (), {}),
    )

    LEGACY_STAGES = (
        ("migrate", ("auth",), {"interactive": False}),
        ("ensure_initial_data", (), {"app_label": "users"}),
        ("ensure_initial_data", (), {"app_label": "object_management"}),
        ("migrate", ("properties",), {"interactive": False}),
        ("ensure_initial_data", (), {"app_label": "properties"}),
        ("migrate", (), {"interactive": False}),
        ("ensure_initial_data", (), {}),
    )

    def _requires_legacy_bootstrap(self):
        loader = MigrationLoader(connection)
        return any(
            key[0] in {"properties", "materials"} and key not in loader.graph.nodes
            for key in loader.replacements
        )

    def handle(self, *args, **options):
        forwarded = {
            "verbosity": options["verbosity"],
            "stdout": self.stdout,
            "stderr": self.stderr,
        }
        if self._requires_legacy_bootstrap():
            stages = self.LEGACY_STAGES
        else:
            stages = self.STAGES
        total = len(stages)
        for index, (command, positional, keyword) in enumerate(stages, 1):
            stage = " ".join((command, *positional))
            if "app_label" in keyword:
                stage = f"{command} --app {keyword['app_label']}"
            self.stdout.write(f"[{index}/{total}] {stage}")
            call_command(command, *positional, **keyword, **forwarded)
        self.stdout.write(self.style.SUCCESS("Database bootstrap complete."))
