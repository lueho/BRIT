from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from utils.object_management.models import UserCreatedObject


class Command(BaseCommand):
    """
    Management command to fix inconsistencies in publication status and metadata.

    This command:
    1. Finds published objects with missing approval metadata and adds it
    2. Validates all objects in review have a submitted_at value
    3. Reports any invalid state transitions detected
    """

    help = "Fix inconsistencies in publication status and metadata"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report issues without fixing them",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Running in dry-run mode. No changes will be made.")
            )

        # Find all models that inherit from UserCreatedObject
        user_created_models = []
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                # Check if this model inherits from UserCreatedObject but is not abstract
                if issubclass(model, UserCreatedObject) and not model._meta.abstract:
                    user_created_models.append(model)

        if not user_created_models:
            self.stdout.write(
                self.style.WARNING("No models inheriting from UserCreatedObject found.")
            )
            return

        self.stdout.write(f"Found {len(user_created_models)} models to process.")

        # Process each model
        for model_class in user_created_models:
            self.process_model(model_class, dry_run)

        self.stdout.write(
            self.style.SUCCESS("Publication inconsistency check complete.")
        )

    def process_model(self, model_class, dry_run):
        """Process a specific model class to fix inconsistencies."""
        model_name = model_class._meta.verbose_name_plural
        self.stdout.write(f"Processing {model_name}...")

        # 1. Find published objects with missing approval metadata
        published_missing_approval = model_class.objects.filter(
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
            approved_at__isnull=True,
        )

        if published_missing_approval.exists():
            count = published_missing_approval.count()
            self.stdout.write(
                self.style.WARNING(
                    f"Found {count} published {model_name} with missing approval metadata"
                )
            )

            if not dry_run:
                now = timezone.now()
                for obj in published_missing_approval:
                    obj.approved_at = now
                    obj.save(update_fields=["approved_at"])
                self.stdout.write(self.style.SUCCESS(f"Fixed {count} objects"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No published {model_name} with missing approval metadata"
                )
            )

        # 2. Validate all objects in review have a submitted_at value
        review_missing_submission = model_class.objects.filter(
            publication_status=UserCreatedObject.STATUS_REVIEW,
            submitted_at__isnull=True,
        )

        if review_missing_submission.exists():
            count = review_missing_submission.count()
            self.stdout.write(
                self.style.WARNING(
                    f"Found {count} {model_name} in review with missing submission metadata"
                )
            )

            if not dry_run:
                now = timezone.now()
                for obj in review_missing_submission:
                    obj.submitted_at = now
                    obj.save(update_fields=["submitted_at"])
                self.stdout.write(self.style.SUCCESS(f"Fixed {count} objects"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No {model_name} in review with missing submission metadata"
                )
            )

        # 3. Report any objects with approval metadata but not published
        invalid_approval = model_class.objects.filter(
            ~Q(publication_status=UserCreatedObject.STATUS_PUBLISHED),
            approved_at__isnull=False,
        )

        if invalid_approval.exists():
            count = invalid_approval.count()
            self.stdout.write(
                self.style.WARNING(
                    f"Found {count} {model_name} with approval metadata but not published. "
                    "This is an inconsistent state."
                )
            )

            if not dry_run:
                for obj in invalid_approval:
                    obj.approved_at = None
                    obj.approved_by = None
                    obj.save(update_fields=["approved_at", "approved_by"])
                self.stdout.write(self.style.SUCCESS(f"Fixed {count} objects"))

        # 4. Report any objects with submission metadata but not in review
        invalid_submission = model_class.objects.filter(
            ~Q(publication_status=UserCreatedObject.STATUS_REVIEW),
            submitted_at__isnull=False,
        )

        if invalid_submission.exists():
            count = invalid_submission.count()
            self.stdout.write(
                self.style.WARNING(
                    f"Found {count} {model_name} with submission metadata but not in review. "
                    "This is an inconsistent state."
                )
            )

            if not dry_run:
                for obj in invalid_submission:
                    obj.submitted_at = None
                    obj.save(update_fields=["submitted_at"])
                self.stdout.write(self.style.SUCCESS(f"Fixed {count} objects"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No {model_name} with submission metadata but not in review"
                )
            )

        # Final check for any objects with invalid approval metadata
        if not invalid_approval.exists():
            self.stdout.write(
                self.style.SUCCESS(f"No {model_name} with invalid approval metadata")
            )
