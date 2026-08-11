"""Temporal catchment boundary snapshots and their integrity rules."""

from datetime import date
from importlib import import_module

from django.contrib.admin.sites import AdminSite
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from maps.admin import CatchmentRevisionModelAdmin
from maps.models import Catchment, CatchmentRevision, LauRegion
from utils.object_management.models import UserCreatedObject


def square(xmin, ymin, xmax, ymax):
    return GEOSGeometry(
        "MULTIPOLYGON((("
        f"{xmin} {ymin}, {xmin} {ymax}, {xmax} {ymax}, "
        f"{xmax} {ymin}, {xmin} {ymin}"
        ")))",
        srid=4326,
    )


class CatchmentRevisionValidityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = Catchment.objects.create(name="Temporal catchment")
        cls.old = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Boundary through 2023",
            effective_from=date(2020, 1, 1),
            effective_to=date(2024, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        cls.current = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Boundary from 2024",
            effective_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def test_valid_on_uses_half_open_effective_periods(self):
        self.assertEqual(
            CatchmentRevision.objects.valid_on(date(2023, 12, 31)).get(),
            self.old,
        )
        self.assertEqual(
            CatchmentRevision.objects.valid_on(date(2024, 1, 1)).get(),
            self.current,
        )

    def test_geometry_has_a_spatial_index(self):
        self.assertTrue(CatchmentRevision._meta.get_field("geom").spatial_index)

    def test_admin_exposes_review_and_approval_workflow(self):
        model_admin = CatchmentRevisionModelAdmin(CatchmentRevision, AdminSite())

        self.assertIn("submit_selected_for_review", model_admin.actions)
        self.assertIn("approve_selected", model_admin.actions)

    def test_admin_locks_immutable_fields_of_published_revisions(self):
        model_admin = CatchmentRevisionModelAdmin(CatchmentRevision, AdminSite())

        locked = model_admin.get_readonly_fields(None, self.old)
        editable = model_admin.get_readonly_fields(None, None)

        for field in ("catchment", "effective_from", "effective_to", "geom", "members"):
            self.assertIn(field, locked)
            self.assertNotIn(field, editable)

    def test_revision_for_date_resolves_the_published_snapshot(self):
        self.assertEqual(self.catchment.revision_for_date(date(2022, 12, 31)), self.old)
        self.assertEqual(
            self.catchment.revision_for_date(date(2024, 12, 31)), self.current
        )

    def test_published_revision_geometry_is_immutable(self):
        self.old.geom = square(0, 0, 3, 1)

        with self.assertRaisesMessage(
            ValidationError, "Published catchment revisions are immutable"
        ):
            self.old.save()

    def test_published_revision_immutability_is_reported_during_validation(self):
        self.old.geom = square(0, 0, 3, 1)

        with self.assertRaisesMessage(
            ValidationError, "Published catchment revisions are immutable"
        ):
            self.old.full_clean()

    def test_deleting_a_catchment_removes_its_revisions(self):
        region = LauRegion.objects.create(
            name="Disposable", lau_name="Disposable", lau_id="disp", cntr_code="DE"
        )
        catchment = Catchment.objects.create(name="Disposable catchment", region=region)
        revision = CatchmentRevision.objects.create(
            catchment=catchment,
            name="Only boundary",
            effective_from=date(2020, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

        catchment.delete()

        self.assertFalse(CatchmentRevision.objects.filter(pk=revision.pk).exists())

    def test_published_revision_members_are_immutable_from_the_region_side(self):
        region = LauRegion.objects.create(
            name="Reverse member", lau_name="Reverse", lau_id="reverse", cntr_code="DE"
        )

        with self.assertRaisesMessage(
            ValidationError, "Published catchment revisions are immutable"
        ):
            region.catchment_revisions.add(self.old)

    def test_published_revision_periods_cannot_overlap(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CatchmentRevision.objects.create(
                    catchment=self.catchment,
                    name="Overlapping boundary",
                    effective_from=date(2023, 1, 1),
                    effective_to=date(2025, 1, 1),
                    geom=square(0, 0, 1, 1),
                    publication_status=UserCreatedObject.STATUS_PUBLISHED,
                )

    def test_private_draft_may_overlap_published_revision(self):
        draft = CatchmentRevision.objects.create(
            catchment=self.catchment,
            name="Candidate successor",
            effective_from=date(2025, 1, 1),
            geom=square(0, 0, 3, 1),
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        self.assertIsNotNone(draft.pk)

    def test_invalid_period_is_rejected(self):
        revision = CatchmentRevision(
            catchment=self.catchment,
            name="Invalid boundary",
            effective_from=date(2024, 1, 2),
            effective_to=date(2024, 1, 1),
            geom=square(0, 0, 1, 1),
        )

        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_approving_successor_closes_and_archives_published_predecessor(self):
        catchment = Catchment.objects.create(name="Successor workflow catchment")
        predecessor = CatchmentRevision.objects.create(
            catchment=catchment,
            name="Original boundary",
            effective_from=date(2020, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor = CatchmentRevision.objects.create(
            catchment=catchment,
            name="Expanded boundary",
            effective_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
        )
        successor.predecessors.add(predecessor)
        successor.submit_for_review()

        successor.approve()

        predecessor.refresh_from_db()
        successor.refresh_from_db()
        self.assertEqual(predecessor.effective_to, date(2024, 1, 1))
        self.assertEqual(
            predecessor.publication_status, UserCreatedObject.STATUS_ARCHIVED
        )
        self.assertEqual(
            successor.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertEqual(catchment.revision_for_date(date(2023, 12, 31)), predecessor)
        self.assertEqual(catchment.revision_for_date(date(2024, 1, 1)), successor)

    def test_approving_overlapping_revision_requires_predecessor_link(self):
        catchment = Catchment.objects.create(name="Missing predecessor catchment")
        CatchmentRevision.objects.create(
            catchment=catchment,
            name="Open boundary",
            effective_from=date(2020, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor = CatchmentRevision.objects.create(
            catchment=catchment,
            name="Unlinked candidate",
            effective_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
        )
        successor.submit_for_review()

        with self.assertRaisesMessage(ValidationError, "overlaps a published period"):
            successor.approve()


class CatchmentRevisionCompositionTests(TestCase):
    def test_create_from_members_snapshots_the_union_and_provenance(self):
        left = LauRegion.objects.create(
            name="Left", lau_name="Left", lau_id="left", cntr_code="DE"
        )
        left.geom = square(0, 0, 1, 1)
        left.save()
        right = LauRegion.objects.create(
            name="Right", lau_name="Right", lau_id="right", cntr_code="DE"
        )
        right.geom = square(1, 0, 2, 1)
        right.save()
        catchment = Catchment.objects.create(name="Composed catchment")

        revision = CatchmentRevision.objects.create_from_members(
            catchment=catchment,
            members=[left, right],
            name="Two-member boundary",
            effective_from=date(2024, 1, 1),
        )

        self.assertSetEqual(
            set(revision.members.values_list("pk", flat=True)), {left.pk, right.pk}
        )
        self.assertAlmostEqual(revision.geom.area, 2.0)
        self.assertTrue(revision.geom.equals(square(0, 0, 2, 1)))


class CatchmentRevisionBackfillNameTests(SimpleTestCase):
    """The backfill must fit the name column for every existing catchment."""

    @staticmethod
    def initial_revision_name(name):
        migration = import_module("maps.migrations.0017_catchment_revisions")
        return migration.initial_revision_name(name)

    def test_long_catchment_names_stay_within_the_name_column(self):
        max_length = CatchmentRevision._meta.get_field("name").max_length

        name = self.initial_revision_name("x" * max_length)

        self.assertLessEqual(len(name), max_length)
        self.assertTrue(name.endswith(" — initial boundary"))

    def test_missing_catchment_name_falls_back_to_a_generic_label(self):
        self.assertEqual(self.initial_revision_name(""), "Catchment — initial boundary")
