import contextlib
import io

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from sources.waste_collection.models import WasteCategory


class FixPublicationInconsistenciesTests(TestCase):
    """Data-quality command for published rows missing approval metadata."""

    def setUp(self):
        self.owner = User.objects.create_user(username="command-owner")

    def _published_without_approval(self, name):
        category = WasteCategory.objects.create(name=name, owner=self.owner)
        # Simulate a pre-workflow row: published without approval metadata.
        WasteCategory.objects.filter(pk=category.pk).update(
            publication_status="published",
            approved_at=None,
            approved_by=None,
        )
        category.refresh_from_db()
        return category

    def _run_command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            call_command("fix_publication_inconsistencies", *args)
        return stdout.getvalue()

    def test_backfills_missing_approval_metadata(self):
        category = self._published_without_approval("Unapproved")

        output = self._run_command()

        category.refresh_from_db()
        self.assertEqual(category.approved_at, category.created_at)
        self.assertEqual(category.approved_by_id, self.owner.pk)
        self.assertIn("missing approval metadata", output)

    def test_backfills_missing_approved_by_only(self):
        category = self._published_without_approval("Partially approved")
        approved_at = timezone.now()
        WasteCategory.objects.filter(pk=category.pk).update(approved_at=approved_at)

        self._run_command()

        category.refresh_from_db()
        self.assertEqual(category.approved_at, approved_at)
        self.assertEqual(category.approved_by_id, self.owner.pk)

    def test_dry_run_reports_without_fixing(self):
        category = self._published_without_approval("Dry run")

        output = self._run_command("--dry-run")

        category.refresh_from_db()
        self.assertIsNone(category.approved_at)
        self.assertIsNone(category.approved_by)
        self.assertIn("missing approval metadata", output)

    def test_keeps_approval_metadata_of_archived_rows(self):
        """archive() retains approval metadata; the cleanup must not erase it."""
        category = self._published_without_approval("Archived")
        self._run_command()
        category.refresh_from_db()
        category.archive()
        approved_at = category.approved_at

        self._run_command()

        category.refresh_from_db()
        self.assertEqual(category.publication_status, "archived")
        self.assertEqual(category.approved_at, approved_at)
        self.assertEqual(category.approved_by_id, self.owner.pk)

    def test_clears_approval_metadata_of_private_rows(self):
        category = WasteCategory.objects.create(name="Private", owner=self.owner)
        WasteCategory.objects.filter(pk=category.pk).update(
            approved_at=timezone.now(), approved_by=self.owner
        )

        self._run_command()

        category.refresh_from_db()
        self.assertIsNone(category.approved_at)
        self.assertIsNone(category.approved_by)
