"""
Bootstraps a BRIT database from scratch.

A fresh database only needs ``migrate`` followed by
``ensure_initial_data``: the schema-only replacement migrations contain no
data operations, and the required default rows are created by the app
initializers. The ``replaces`` metadata on the baselines lets databases
with fully applied legacy histories adopt the replacements automatically.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Applies migrations and seeds initial data by running plain "
        "migrate followed by ensure_initial_data. Safe to run repeatedly."
    )

    requires_system_checks = []

    STAGES = (
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
