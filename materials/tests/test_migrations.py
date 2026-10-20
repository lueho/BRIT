"""Tests for retroactive data migrations in the materials app."""

import importlib

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from materials.models import MaterialCategory

backfill_module = importlib.import_module(
    "materials.migrations.0033_backfill_approval_metadata"
)


class BackfillApprovalMetadataTests(TestCase):
    """Retroactive backfill for pre-workflow published rows (issue #93)."""

    def setUp(self):
        self.owner = User.objects.create_user(username="backfill-owner")

    def _published_without_approval(self, name):
        category = MaterialCategory.objects.create(name=name, owner=self.owner)
        # Simulate a pre-workflow row: published without approval metadata.
        MaterialCategory.objects.filter(pk=category.pk).update(
            publication_status="published",
            approved_at=None,
            approved_by=None,
        )
        category.refresh_from_db()
        return category

    def _run_backfill(self):
        backfill_module.backfill_approval_metadata(apps, None)

    def test_backfills_missing_approval_metadata(self):
        category = self._published_without_approval("Backfill Category")

        self._run_backfill()

        category.refresh_from_db()
        self.assertEqual(category.approved_at, category.created_at)
        self.assertEqual(category.approved_by_id, self.owner.pk)

    def test_backfills_missing_approved_by_only(self):
        category = self._published_without_approval("Partial Category")
        approved_at = timezone.now()
        MaterialCategory.objects.filter(pk=category.pk).update(approved_at=approved_at)

        self._run_backfill()

        category.refresh_from_db()
        self.assertEqual(category.approved_at, approved_at)
        self.assertEqual(category.approved_by_id, self.owner.pk)

    def test_leaves_properly_approved_rows_untouched(self):
        moderator = User.objects.create_user(username="backfill-moderator")
        category = self._published_without_approval("Approved Category")
        approved_at = timezone.now()
        MaterialCategory.objects.filter(pk=category.pk).update(
            approved_at=approved_at, approved_by=moderator
        )

        self._run_backfill()

        category.refresh_from_db()
        self.assertEqual(category.approved_at, approved_at)
        self.assertEqual(category.approved_by_id, moderator.pk)

    def test_leaves_non_published_rows_untouched(self):
        category = MaterialCategory.objects.create(
            name="Private Category", owner=self.owner
        )

        self._run_backfill()

        category.refresh_from_db()
        self.assertEqual(category.publication_status, MaterialCategory.STATUS_PRIVATE)
        self.assertIsNone(category.approved_at)
        self.assertIsNone(category.approved_by)
