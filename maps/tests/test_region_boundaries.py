"""Effective-dated region boundaries (year-accurate municipality geometry)."""

import json
from datetime import UTC, date, datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from maps.models import (
    Catchment,
    CatchmentRevision,
    GeoPolygon,
    Region,
    RegionBoundary,
    dated_region_geom_expression,
)
from maps.serializers import RegionDatedGeoFeatureSerializer
from maps.utils import iter_geojson_features
from utils.object_management.models import ReviewAction, UserCreatedObject
from utils.object_management.services import perform_transition


def square(xmin, ymin, xmax, ymax):
    return GEOSGeometry(
        "MULTIPOLYGON((("
        f"{xmin} {ymin}, {xmin} {ymax}, {xmax} {ymax}, "
        f"{xmax} {ymin}, {xmin} {ymin}"
        ")))",
        srid=4326,
    )


def region_with_borders(name, geom):
    region = Region.objects.create(
        name=name,
        country="Germany",
        publication_status=UserCreatedObject.STATUS_PUBLISHED,
    )
    region.borders = GeoPolygon.objects.create(geom=geom)
    region.save()
    return region


class RegionBoundaryQuerySetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = region_with_borders("Test region", square(0, 0, 1, 1))
        cls.old = RegionBoundary.objects.create(
            region=cls.region,
            name="Boundary through 2023",
            valid_from=date(2020, 1, 1),
            valid_to=date(2024, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        cls.current = RegionBoundary.objects.create(
            region=cls.region,
            name="Boundary from 2024",
            valid_from=date(2024, 1, 1),
            valid_to=date(2025, 1, 1),
            geom=square(0, 0, 2, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def test_valid_on_uses_half_open_periods(self):
        self.assertEqual(
            RegionBoundary.objects.valid_on(date(2023, 12, 31)).get(),
            self.old,
        )
        self.assertEqual(
            RegionBoundary.objects.valid_on(date(2024, 1, 1)).get(),
            self.current,
        )

    def test_valid_on_honours_open_ended_periods(self):
        dissolved = RegionBoundary.objects.create(
            region=self.region,
            name="Open-ended tail",
            valid_from=date(2025, 1, 1),
            geom=square(0, 0, 3, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(
            RegionBoundary.objects.valid_on(date(2030, 6, 1)).get(),
            dissolved,
        )

    def test_valid_on_filters_dates_only(self):
        """``valid_on`` scopes by period; status scoping is the caller's job."""
        draft = RegionBoundary.objects.create(
            region=self.region,
            name="Draft boundary",
            valid_from=date(2020, 1, 1),
            geom=square(9, 9, 10, 10),
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.assertIn(
            draft,
            RegionBoundary.objects.valid_on(date(2022, 1, 1)),
        )
        self.assertNotIn(
            draft,
            RegionBoundary.objects.valid_on(date(2022, 1, 1)).filter(
                publication_status__in=("published", "archived")
            ),
        )

    def test_geometry_has_a_spatial_index(self):
        self.assertTrue(RegionBoundary._meta.get_field("geom").spatial_index)


class RegionGeomOnTests(TestCase):
    def test_falls_back_to_borders_without_boundary_rows(self):
        region = region_with_borders("Timeless", square(0, 0, 1, 1))
        self.assertEqual(region.geom_on(date(2024, 6, 1)), square(0, 0, 1, 1))

    def test_returns_dated_boundary_when_valid(self):
        region = region_with_borders("Dated", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=region,
            name="Post-merger",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(region.geom_on(date(2024, 6, 1)), square(0, 0, 2, 1))

    def test_returns_none_when_no_boundary_is_valid(self):
        """A dissolved region must not resolve to geometry after dissolution."""
        region = region_with_borders("Dissolved", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=region,
            name="Until dissolution",
            valid_to=date(2024, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertIsNone(region.geom_on(date(2024, 6, 1)))
        self.assertEqual(region.geom_on(date(2023, 6, 1)), square(0, 0, 1, 1))

    def test_unpublished_boundary_rows_fall_back_to_borders(self):
        region = region_with_borders("Draft only", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=region,
            name="Draft",
            valid_from=date(2020, 1, 1),
            geom=square(9, 9, 10, 10),
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.assertEqual(region.geom_on(date(2024, 6, 1)), square(0, 0, 1, 1))


class RegionDatedGeoJSONTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = region_with_borders("Dated region", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=cls.region,
            name="Post-merger",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        cls.dissolved = region_with_borders("Dissolved", square(5, 5, 6, 6))
        RegionBoundary.objects.create(
            region=cls.dissolved,
            name="Until dissolution",
            valid_to=date(2024, 1, 1),
            geom=square(5, 5, 6, 6),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def _geojson(self, **params):
        response = self.client.get(reverse("api-region-geojson"), params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_dated_request_serves_boundary_geometry(self):
        data = self._geojson(id=self.region.pk, date="2024-06-01")
        self.assertEqual(len(data["features"]), 1)
        ring = data["features"][0]["geometry"]["coordinates"][0][0]
        self.assertIn([2.0, 1.0], ring)
        self.assertNotIn([1.0, 0.0], ring)

    def test_dated_request_excludes_dissolved_regions(self):
        data = self._geojson(date="2024-06-01")
        ids = {f["properties"]["id"] for f in data["features"]}
        self.assertIn(self.region.pk, ids)
        self.assertNotIn(self.dissolved.pk, ids)

    def test_dissolved_region_still_served_before_dissolution(self):
        data = self._geojson(id=self.dissolved.pk, date="2023-06-01")
        self.assertEqual(len(data["features"]), 1)

    def test_request_without_date_uses_timeless_borders(self):
        data = self._geojson(id=self.region.pk)
        self.assertEqual(len(data["features"]), 1)
        ring = data["features"][0]["geometry"]["coordinates"][0][0]
        self.assertIn([1.0, 1.0], ring)
        self.assertNotIn([2.0, 0.0], ring)


class RegionBoundaryWorkflowTests(TestCase):
    """The review workflow closes predecessors like CatchmentRevision."""

    def _published_boundary(self, region, **overrides):
        kwargs = {
            "region": region,
            "name": "Published boundary",
            "valid_from": date(2020, 1, 1),
            "geom": square(0, 0, 1, 1),
            "publication_status": UserCreatedObject.STATUS_PUBLISHED,
        }
        kwargs.update(overrides)
        return RegionBoundary.objects.create(**kwargs)

    def test_approving_successor_closes_and_archives_predecessor(self):
        region = region_with_borders("Workflow region", square(0, 0, 1, 1))
        predecessor = self._published_boundary(region, valid_to=None)
        successor = RegionBoundary.objects.create(
            region=region,
            name="Expanded boundary",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
        )
        successor.predecessors.add(predecessor)
        successor.submit_for_review()

        approver = User.objects.create(username="boundary_approver", is_superuser=True)
        perform_transition(
            approver, successor, "approve", expected_revision=successor.content_revision
        )
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(RegionBoundary),
                object_id=predecessor.pk,
                action=ReviewAction.ACTION_ARCHIVED,
                user=approver,
            ).exists()
        )

        predecessor.refresh_from_db()
        successor.refresh_from_db()
        self.assertEqual(predecessor.valid_to, date(2024, 1, 1))
        self.assertEqual(
            predecessor.publication_status, UserCreatedObject.STATUS_ARCHIVED
        )
        self.assertEqual(
            successor.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertEqual(region.geom_on(date(2023, 12, 31)), square(0, 0, 1, 1))
        self.assertEqual(region.geom_on(date(2024, 1, 1)), square(0, 0, 2, 1))

    def test_approval_preserves_archived_history_and_rolls_back_other_closures(self):
        region = region_with_borders("Historical overlap", square(0, 0, 1, 1))
        current = self._published_boundary(region, valid_to=date(2025, 1, 1))
        archived = self._published_boundary(
            region,
            valid_from=date(2025, 1, 1),
            publication_status="archived",
        )
        successor = RegionBoundary.objects.create(
            region=region,
            name="Overlapping",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
        )
        successor.predecessors.add(current, archived)
        successor.submit_for_review()
        approver = User.objects.create(username="boundary_approver", is_superuser=True)
        with self.assertRaisesMessage(ValidationError, "overlaps"):
            perform_transition(
                approver,
                successor,
                "approve",
                expected_revision=successor.content_revision,
            )
        current.refresh_from_db()
        archived.refresh_from_db()
        successor.refresh_from_db()
        self.assertEqual(
            (current.publication_status, current.valid_to),
            ("published", date(2025, 1, 1)),
        )
        self.assertIsNone(archived.valid_to)
        self.assertEqual(successor.publication_status, "review")
        self.assertFalse(
            ReviewAction.objects.filter(
                action=ReviewAction.ACTION_ARCHIVED, user=approver
            ).exists()
        )

    def test_reviewed_dissolution_ends_an_open_boundary_without_a_successor_shape(self):
        region = region_with_borders("Retired municipality", square(5, 5, 6, 6))
        previous = self._published_boundary(region)
        dissolution = RegionBoundary.objects.create(
            region=region,
            name="Dissolution",
            valid_from=date(2025, 1, 1),
            is_dissolution=True,
        )
        dissolution.predecessors.add(previous)
        dissolution.submit_for_review()
        moderator = User.objects.create(
            username="boundary_moderator", is_superuser=True
        )
        perform_transition(
            moderator,
            dissolution,
            "approve",
            expected_revision=dissolution.content_revision,
        )
        self.assertEqual(region.geom_on(date(2024, 12, 31)), previous.geom)
        self.assertIsNone(region.geom_on(date(2025, 1, 1)))
        response = self.client.get(
            reverse("api-region-geojson"), {"id": region.pk, "date": "2025-01-01"}
        )
        self.assertEqual(response.json()["features"], [])

    def test_approving_overlapping_boundary_requires_predecessor_link(self):
        region = region_with_borders("Overlap region", square(0, 0, 1, 1))
        self._published_boundary(region, valid_to=None)
        successor = RegionBoundary.objects.create(
            region=region,
            name="Unlinked candidate",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 2, 1),
        )
        successor.submit_for_review()

        approver = User.objects.create(username="boundary_approver")
        with self.assertRaisesMessage(ValidationError, "overlaps a published"):
            successor.approve(user=approver)

    def test_successor_without_valid_from_is_rejected(self):
        region = region_with_borders("Undated successor region", square(0, 0, 1, 1))
        predecessor = self._published_boundary(region, valid_to=None)
        successor = RegionBoundary.objects.create(
            region=region,
            name="Undated candidate",
            geom=square(0, 0, 2, 1),
        )
        successor.predecessors.add(predecessor)
        successor.submit_for_review()

        approver = User.objects.create(username="boundary_approver")
        with self.assertRaisesMessage(ValidationError, "needs a valid-from"):
            successor.approve(user=approver)

    def test_published_boundary_snapshot_is_immutable(self):
        region = region_with_borders("Immutable region", square(0, 0, 1, 1))
        boundary = self._published_boundary(region)
        boundary.geom = square(0, 0, 9, 9)
        with self.assertRaisesMessage(ValidationError, "immutable"):
            boundary.save()


class RegionDatedGeoJSONStreamingTests(TestCase):
    """Streaming must defer a concrete field while serving dated_geom."""

    @classmethod
    def setUpTestData(cls):
        cls.region = region_with_borders("Streamed region", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=cls.region,
            name="Post-merger",
            valid_from=date(2024, 1, 1),
            geom=MultiPolygon(square(0, 0, 2, 1)[0], square(3, 0, 4, 1)[0], srid=4326),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def test_streaming_serves_dated_geometry(self):
        queryset = Region.objects.filter(pk=self.region.pk).annotate(
            dated_geom=dated_region_geom_expression(date(2024, 6, 1))
        )
        chunks = iter_geojson_features(
            queryset,
            RegionDatedGeoFeatureSerializer,
            "dated_geom",
            geometry_defer_field="borders__geom",
        )
        data = json.loads(b"".join(chunks))
        self.assertEqual(len(data["features"]), 1)
        ring = data["features"][0]["geometry"]["coordinates"][0][0]
        self.assertIn([2.0, 1.0], ring)

    def test_endpoint_streams_dated_responses(self):
        with patch("maps.mixins.STREAMING_THRESHOLD", 0):
            response = self.client.get(
                reverse("api-region-geojson"),
                {"id": self.region.pk, "date": "2024-06-01", "stream": "true"},
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(b"".join(response.streaming_content))
        ring = data["features"][0]["geometry"]["coordinates"][0][0]
        self.assertIn([2.0, 1.0], ring)

    def test_vertex_threshold_counts_the_served_boundary_on_both_endpoints(self):
        catchment = Catchment.objects.create(
            region=self.region, name="Dated catchment", publication_status="published"
        )
        with patch("maps.mixins.GEOJSON_MAX_BUFFERED_POINTS", 6):
            for basename, pk in (
                ("region", self.region.pk),
                ("catchment", catchment.pk),
            ):
                with self.subTest(endpoint=basename):
                    response = self.client.get(
                        reverse(f"api-{basename}-geojson"),
                        {"id": pk, "date": "2024-06-01"},
                    )
                    self.assertEqual(response["X-Cache-Status"], "STREAM")
                    geometries = json.loads(b"".join(response.streaming_content))[
                        "features"
                    ]
                    self.assertEqual(len(geometries[0]["geometry"]["coordinates"]), 2)


class RegionDatedGeoJSONBboxTests(TestCase):
    """bbox must filter the resolved dated geometry, not timeless borders."""

    @classmethod
    def setUpTestData(cls):
        cls.region = region_with_borders("Moved region", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=cls.region,
            name="Relocated",
            valid_from=date(2024, 1, 1),
            geom=square(10, 10, 11, 11),
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def _geojson(self, **params):
        response = self.client.get(reverse("api-region-geojson"), params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_bbox_inside_dated_geometry_includes_region(self):
        data = self._geojson(id=self.region.pk, date="2024-06-01", bbox="10,10,11,11")
        self.assertEqual(len(data["features"]), 1)

    def test_bbox_inside_timeless_borders_excludes_region(self):
        data = self._geojson(id=self.region.pk, date="2024-06-01", bbox="0,0,1,1")
        self.assertEqual(len(data["features"]), 0)


class RegionDatedStatsTests(TestCase):
    """Boundary history must not multiply feature counts or point totals."""

    @classmethod
    def setUpTestData(cls):
        cls.region = region_with_borders("Multi-boundary region", square(0, 0, 1, 1))
        for year in (2020, 2022, 2024):
            RegionBoundary.objects.create(
                region=cls.region,
                name=f"Boundary {year}",
                valid_from=date(year, 1, 1),
                valid_to=date(year + 2, 1, 1),
                geom=square(0, 0, 1, 1),
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_feature_count_is_not_multiplied_by_boundary_rows(self):
        response = self.client.get(
            reverse("api-region-geojson"),
            {"id": self.region.pk, "date": "2021-06-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Total-Count"], "1")
        self.assertEqual(len(response.json()["features"]), 1)


class RegionBoundaryCacheInvalidationTests(TestCase):
    def test_boundary_invalidation_waits_for_commit_and_skips_rollbacks(self):
        region = region_with_borders("Caches", square(0, 0, 1, 1))
        with patch("maps.signals.clear_geojson_cache_pattern") as clear:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    RegionBoundary.objects.create(
                        region=region, name="Rolled back", geom=square(0, 0, 2, 1)
                    )
                    transaction.set_rollback(True)
            clear.assert_not_called()
            with self.captureOnCommitCallbacks(execute=True):
                boundary = RegionBoundary.objects.create(
                    region=region, name="Effective", geom=square(0, 0, 2, 1)
                )
                clear.assert_not_called()
            patterns = [
                "region_geojson:*",
                "catchment_geojson:*",
                "waste_atlas_change_overlay:*",
            ]
            self.assertEqual([call.args[0] for call in clear.call_args_list], patterns)
            clear.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                boundary.delete()
                clear.assert_not_called()
            self.assertEqual([call.args[0] for call in clear.call_args_list], patterns)

    def test_subsecond_publication_rotates_overlay_and_geojson_payload(self):
        from sources.waste_collection.waste_atlas.viewsets import (
            _change_overlay_cache_key,
        )

        region = region_with_borders("Subsecond publication", square(0, 0, 1, 1))
        catchment = Catchment.objects.create(region=region, name="Coverage")
        ids = {catchment.pk}
        url = reverse("api-region-geojson")
        params = {"id": region.pk, "date": "2024-06-01"}
        stamp = datetime(2024, 1, 1, 12, tzinfo=UTC)
        with patch(
            "ambient_toolbox.models.now", return_value=stamp.replace(microsecond=100)
        ):
            previous = RegionBoundary.objects.create(
                region=region,
                name="Earlier",
                geom=square(0, 0, 2, 1),
                publication_status="published",
            )
        successor = RegionBoundary.objects.create(
            region=region,
            name="Successor",
            valid_from=date(2024, 1, 1),
            geom=square(0, 0, 3, 1),
        )
        successor.predecessors.add(previous)
        successor.submit_for_review()
        approver = User.objects.create(username="boundary_approver", is_superuser=True)
        before_key = _change_overlay_cache_key(ids, 2023, ids, 2024)
        before = self.client.get(url, params)
        self.assertEqual(before.status_code, 200)
        self.assertIn(
            [2.0, 1.0], before.json()["features"][0]["geometry"]["coordinates"][0][0]
        )
        # TestCase keeps on_commit callbacks pending, so the previous payload still exists.
        published_at = stamp.replace(microsecond=200)
        with (
            patch("ambient_toolbox.models.now", return_value=published_at),
            patch("maps.models.timezone.now", return_value=published_at),
        ):
            perform_transition(
                approver,
                successor,
                "approve",
                expected_revision=successor.content_revision,
            )
        self.assertNotEqual(before_key, _change_overlay_cache_key(ids, 2023, ids, 2024))
        after = self.client.get(url, params)
        self.assertNotEqual(before["X-Data-Version"], after["X-Data-Version"])
        self.assertIn(
            [3.0, 1.0], after.json()["features"][0]["geometry"]["coordinates"][0][0]
        )


class AtlasFallbackBatchTests(TestCase):
    """Atlas fallbacks resolve dated geometry without per-catchment queries."""

    def test_revision_snapshots_batches_dated_resolution(self):
        from sources.waste_collection.waste_atlas.viewsets import _revision_snapshots

        catchments = [
            Catchment.objects.create(
                name=f"Fallback {i}",
                region=region_with_borders(f"Region {i}", square(i, 0, i + 1, 1)),
            )
            for i in range(3)
        ]
        ids = [c.pk for c in catchments]
        with self.assertNumQueries(2):
            snapshots = _revision_snapshots(ids, 2024)
        self.assertEqual(len(snapshots), 3)

    def test_acpv_outline_uses_the_same_effective_revision_as_the_map(self):
        from sources.waste_collection.models import CollectionCatchment
        from sources.waste_collection.waste_atlas import viewsets as atlas

        region = region_with_borders("Dissolved municipality", square(0, 0, 1, 1))
        RegionBoundary.objects.create(
            region=region,
            name="Until dissolution",
            valid_to=date(2024, 1, 1),
            geom=square(0, 0, 1, 1),
            publication_status="published",
        )
        catchment = CollectionCatchment.objects.create(
            region=region, name="Continuing collection area"
        )
        revision = CatchmentRevision.objects.create(
            catchment=catchment,
            name="Recorded service area",
            geom=square(2, 0, 4, 1),
            publication_status="published",
        )
        rows = [{"acpv_group_key": "group", "catchment_id": catchment.pk}]
        with (
            patch.object(atlas, "_get_collection_amount", return_value=rows),
            self.assertNumQueries(1),
        ):
            outlines = atlas._get_acpv_outline_geojson("DE", 2024, ())
        (feature,) = outlines["features"]
        self.assertTrue(
            GEOSGeometry(json.dumps(feature["geometry"])).equals(revision.geom)
        )
