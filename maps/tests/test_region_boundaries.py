"""Effective-dated region boundaries (year-accurate municipality geometry)."""

from datetime import date

from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase
from django.urls import reverse

from maps.models import GeoPolygon, Region, RegionBoundary
from utils.object_management.models import UserCreatedObject


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
