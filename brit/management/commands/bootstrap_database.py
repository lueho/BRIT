"""
Bootstraps a BRIT database from scratch.

A fresh database cannot run ``migrate`` straight through: the materials
migration ``0006_materialpropertyvalue_unit`` needs the default owner user and
the default unit to exist while it executes. This command therefore applies
the schema and the initial data in stages, and is equally safe on a database
that has already been initialized.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Applies migrations and seeds initial data in the order a fresh "
        "database requires. Safe to run repeatedly."
    )

    requires_system_checks = []

    STAGES = (
        ("migrate", ("auth",), {"interactive": False}),
        ("ensure_initial_data", (), {"app_label": "users"}),
        ("ensure_initial_data", (), {"app_label": "object_management"}),
        ("migrate", ("properties",), {"interactive": False}),
        ("ensure_initial_data", (), {"app_label": "properties"}),
        ("migrate", (), {"interactive": False}),
        ("ensure_initial_data", (), {}),
    )

    def handle(self, *args, **options):
        forwarded = {
            "verbosity": options["verbosity"],
            "stdout": self.stdout,
            "stderr": self.stderr,
        }
        total = len(self.STAGES)
        for index, (command, positional, keyword) in enumerate(self.STAGES, 1):
            stage = " ".join((command, *positional))
            if "app_label" in keyword:
                stage = f"{command} --app {keyword['app_label']}"
            self.stdout.write(f"[{index}/{total}] {stage}")
            call_command(command, *positional, **keyword, **forwarded)
        self.stdout.write(self.style.SUCCESS("Database bootstrap complete."))
