from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.roles import is_privileged_permission, role_state


class Command(BaseCommand):
    help = (
        "Report or reconcile managed role permissions. "
        "Default is a dry-run; use --apply to add missing grants and revoke "
        "privileged grants outside the manifest, or --check to fail on drift."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Add missing required permissions to managed roles and revoke "
                "moderation/administration grants the manifest does not require."
            ),
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit with CommandError if managed roles drift from the manifest.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["check"]:
            raise CommandError("--apply and --check are mutually exclusive.")
        state, missing_rows = role_state()
        for role, info in state.items():
            missing = sorted(
                f"{p.content_type.app_label}.{p.codename}" for p in info["missing"]
            )
            extraneous = sorted(
                f"{p.content_type.app_label}.{p.codename}" for p in info["extraneous"]
            )
            self.stdout.write(
                f"{role}: missing={len(missing)} extraneous={len(extraneous)}"
            )
            for perm in missing:
                self.stdout.write(f"  missing {perm}")
            for perm in extraneous:
                self.stdout.write(f"  extraneous {perm}")
        if missing_rows:
            rows = ", ".join(f"{label}.{codename}" for label, codename in missing_rows)
            raise CommandError(
                f"Required permission rows do not exist: {rows}. "
                "Run migrations before synchronizing roles."
            )
        if options["apply"]:
            with transaction.atomic():
                for role, info in state.items():
                    group, created = Group.objects.get_or_create(name=role)
                    if created:
                        self.stdout.write(f"created group {role}")
                    if info["missing"]:
                        group.permissions.add(*info["missing"])
                        self.stdout.write(
                            f"{role}: added {len(info['missing'])} permissions"
                        )
                    privileged = [
                        p for p in info["extraneous"] if is_privileged_permission(p)
                    ]
                    if privileged:
                        group.permissions.remove(*privileged)
                        self.stdout.write(
                            f"{role}: revoked {len(privileged)} privileged permissions"
                        )
            return
        if options["check"]:
            drifted = [
                role
                for role, info in state.items()
                if info["missing"] or info["extraneous"]
            ]
            if drifted:
                raise CommandError("Role drift detected on: " + ", ".join(drifted))
            self.stdout.write("no drift")
            return
        self.stdout.write("dry-run: no changes applied")
