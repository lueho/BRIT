"""
Approve all Swedish 2024 CPVs with proper review actions.
Usage: python manage.py approve_swedish_2024_cpvs --username=phillipp [--dry-run]
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from sources.waste_collection.models import CollectionPropertyValue
from utils.object_management.models import ReviewAction

User = get_user_model()


class Command(BaseCommand):
    help = "Approve all Swedish 2024 CPVs with proper review actions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", type=str, required=True, help="Username of the approver"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        username = options["username"]
        dry_run = options["dry_run"]

        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(f"User '{username}' not found")
            return

        self.stdout.write(f"Using approver: {user.username} (id={user.id})")

        # Get content type for CollectionPropertyValue
        ct = ContentType.objects.get(
            app_label="waste_collection", model="collectionpropertyvalue"
        )
        self.stdout.write(f"Content type: {ct.app_label}.{ct.model} (id={ct.id})")

        # Find all Swedish 2024 CPVs in review status
        cpvs = CollectionPropertyValue.objects.filter(
            year=2024,
            publication_status="review",
            collection__catchment__region__country="SE",
        ).select_related("collection__catchment__region")

        total = cpvs.count()
        self.stdout.write(f"Found {total} Swedish 2024 CPVs in review status")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            for cpv in cpvs[:10]:
                self.stdout.write(
                    f"  Would approve CPV {cpv.id} ({cpv.collection.name})"
                )
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        # Approve each CPV and create review action
        approved_count = 0
        with transaction.atomic():
            for cpv in cpvs:
                # Update CPV status
                cpv.publication_status = "published"
                cpv.approved_by = user
                cpv.save(
                    update_fields=["publication_status", "approved_by", "approved_at"]
                )

                # Create review action
                ReviewAction.objects.create(
                    content_type=ct,
                    object_id=cpv.id,
                    action=ReviewAction.ACTION_APPROVED,
                    user=user,
                    comment="Bulk approval of Swedish 2024 collection property values",
                )
                approved_count += 1

                if approved_count % 50 == 0:
                    self.stdout.write(f"  Progress: {approved_count}/{total}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully approved {approved_count} Swedish 2024 CPVs with review actions"
            )
        )
