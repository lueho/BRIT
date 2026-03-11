"""
Phase 1 Unit Consolidation: Merge exact duplicates.

This command:
1. Migrates references from unit id 45 ("-") to unit id 1 ("No unit")
2. Deletes duplicate unit id 50 ("No unit" with dimensionless=False)

Usage:
    # Dry run (default) - shows what would be changed
    docker compose exec web python manage.py consolidate_units_phase1

    # Execute the consolidation
    docker compose exec web python manage.py consolidate_units_phase1 --execute
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ForeignKey, ManyToManyField

from utils.properties.models import Unit

# Mapping: {duplicate_unit_id: canonical_unit_id}
PHASE1_MIGRATIONS = {
    45: 1,  # "-" -> "No unit"
    50: 1,  # Duplicate "No unit" -> canonical "No unit"
}

# Units to delete after migration (must have no remaining references)
UNITS_TO_DELETE = [45, 50]  # "-" and "No unit" with dimensionless=False


def get_unit_fk_models():
    """
    Find all models that have ForeignKey or ManyToManyField to Unit.
    Returns list of (model_class, field_name, field_type) tuples.
    """
    from django.apps import apps
    from django.db.models import CharField

    unit_models = []
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            for field in model._meta.get_fields():
                if isinstance(field, ForeignKey) and field.related_model == Unit:
                    unit_models.append((model, field.name, "fk"))
                elif isinstance(field, ManyToManyField) and field.related_model == Unit:
                    unit_models.append((model, field.name, "m2m"))
                # Also capture CharField named 'unit' (legacy pattern)
                elif isinstance(field, CharField) and field.name == "unit":
                    unit_models.append((model, field.name, "char"))
    return unit_models


class Command(BaseCommand):
    help = "Phase 1: Consolidate duplicate units (dry-run by default)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Execute the consolidation (default is dry-run)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output",
        )

    def handle(self, *args, **options):
        dry_run = not options["execute"]
        verbose = options["verbose"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
            self.stdout.write("Use --execute to perform the consolidation\n")
        else:
            self.stdout.write(
                self.style.SUCCESS("EXECUTE MODE - Changes will be applied")
            )

        # Verify canonical units exist
        try:
            canonical_unit = Unit.objects.get(id=1)
            self.stdout.write(f"\nCanonical 'No unit' (id=1): {canonical_unit.name}")
        except Unit.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("ERROR: Canonical unit id=1 ('No unit') not found!")
            )
            return

        # Check duplicate units
        self.stdout.write("\n--- Checking Duplicate Units ---")
        for dup_id, canon_id in PHASE1_MIGRATIONS.items():
            try:
                dup_unit = Unit.objects.get(id=dup_id)
                canon_unit = Unit.objects.get(id=canon_id)
                self.stdout.write(
                    f"  Duplicate id={dup_id} ('{dup_unit.name}') -> "
                    f"Canonical id={canon_id} ('{canon_unit.name}')"
                )
            except Unit.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Unit id={dup_id} not found (may already be migrated)"
                    )
                )

        for del_id in UNITS_TO_DELETE:
            try:
                del_unit = Unit.objects.get(id=del_id)
                self.stdout.write(f"  To delete: id={del_id} ('{del_unit.name}')")
            except Unit.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Unit id={del_id} not found (may already be deleted)"
                    )
                )

        # Find all models with FK to Unit
        unit_models = get_unit_fk_models()
        self.stdout.write(f"\n--- Found {len(unit_models)} model(s) with Unit FK ---")
        if verbose:
            for model, field_name, field_type in unit_models:
                self.stdout.write(f"  {model.__name__}.{field_name} ({field_type})")

        # Count references that will be migrated
        self.stdout.write("\n--- Reference Counts ---")
        total_to_migrate = 0
        for dup_id, _canon_id in PHASE1_MIGRATIONS.items():
            try:
                dup_unit = Unit.objects.get(id=dup_id)
            except Unit.DoesNotExist:
                continue

            for model, field_name, field_type in unit_models:
                if field_type == "fk":
                    count = model.objects.filter(**{field_name: dup_unit}).count()
                elif field_type == "char":
                    # CharField stores unit name as string
                    count = model.objects.filter(**{field_name: dup_unit.name}).count()
                else:  # m2m
                    count = model.objects.filter(
                        **{f"{field_name}__id": dup_unit.id}
                    ).count()

                if count > 0:
                    self.stdout.write(
                        f"  {model.__name__}.{field_name}: {count} references to "
                        f"unit id={dup_id} ('{dup_unit.name}')"
                    )
                    total_to_migrate += count

        self.stdout.write(f"\nTotal references to migrate: {total_to_migrate}")

        if dry_run:
            self.stdout.write(
                "\n" + self.style.SUCCESS("Dry run completed. No changes made.")
            )
            self.stdout.write("Run with --execute to apply changes.")
            return

        # Execute migrations
        self.stdout.write("\n--- Executing Migrations ---")

        with transaction.atomic():
            for dup_id, canon_id in PHASE1_MIGRATIONS.items():
                try:
                    dup_unit = Unit.objects.get(id=dup_id)
                    canon_unit = Unit.objects.get(id=canon_id)
                except Unit.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping: Unit id={dup_id} or id={canon_id} not found"
                        )
                    )
                    continue

                for model, field_name, field_type in unit_models:
                    if field_type == "fk":
                        qs = model.objects.filter(**{field_name: dup_unit})
                        count = qs.count()
                        if count > 0:
                            qs.update(**{field_name: canon_unit})
                            self.stdout.write(
                                f"  Updated {model.__name__}: {count} rows "
                                f"({field_name}: {dup_id} -> {canon_id})"
                            )
                    elif field_type == "char":
                        # CharField: update by unit name
                        qs = model.objects.filter(**{field_name: dup_unit.name})
                        count = qs.count()
                        if count > 0:
                            qs.update(**{field_name: canon_unit.name})
                            self.stdout.write(
                                f"  Updated {model.__name__}: {count} rows "
                                f"({field_name}: '{dup_unit.name}' -> '{canon_unit.name}')"
                            )
                    else:  # m2m
                        instances = list(
                            model.objects.filter(**{f"{field_name}__id": dup_unit.id})
                        )
                        if instances:
                            for instance in instances:
                                getattr(instance, field_name).remove(dup_unit)
                                getattr(instance, field_name).add(canon_unit)
                            self.stdout.write(
                                f"  Updated {model.__name__}: {len(instances)} instances "
                                f"({field_name}: {dup_id} -> {canon_id})"
                            )

            # Delete duplicate units
            self.stdout.write("\n--- Deleting Duplicate Units ---")
            for del_id in UNITS_TO_DELETE:
                try:
                    del_unit = Unit.objects.get(id=del_id)
                    # Verify no remaining references
                    has_refs = False
                    for model, field_name, field_type in unit_models:
                        if field_type == "fk":
                            if model.objects.filter(**{field_name: del_unit}).exists():
                                has_refs = True
                                break
                        elif field_type == "char":
                            if model.objects.filter(
                                **{field_name: del_unit.name}
                            ).exists():
                                has_refs = True
                                break
                        else:  # m2m
                            if model.objects.filter(
                                **{f"{field_name}__id": del_unit.id}
                            ).exists():
                                has_refs = True
                                break

                    if has_refs:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Cannot delete unit id={del_id}: still has references!"
                            )
                        )
                    else:
                        name = del_unit.name
                        del_unit.delete()
                        self.stdout.write(f"  Deleted unit id={del_id} ('{name}')")
                except Unit.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Unit id={del_id} already deleted")
                    )

        self.stdout.write("\n" + self.style.SUCCESS("Phase 1 consolidation completed!"))

        # Verification
        self.stdout.write("\n--- Verification ---")
        remaining_units = Unit.objects.count()
        self.stdout.write(f"Total units in database: {remaining_units}")

        for dup_id in list(PHASE1_MIGRATIONS.keys()) + UNITS_TO_DELETE:
            if Unit.objects.filter(id=dup_id).exists():
                self.stdout.write(
                    self.style.WARNING(f"  WARNING: Unit id={dup_id} still exists")
                )
            else:
                self.stdout.write(f"  Unit id={dup_id}: successfully removed")
