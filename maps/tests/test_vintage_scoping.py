"""User-facing NUTS queries must show one vintage, not every vintage at once."""

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.urls import reverse

from ..models import GeoPolygon, NutsRegion, NutsVintage, Region
from ..utils import get_nuts_region_cache_key


def _x_origin(feature):
    """First x coordinate of a feature, identifying which vintage it came from."""
    return feature["geometry"]["coordinates"][0][0][0][0]


def _borders(offset=0.0):
    return GeoPolygon.objects.create(
        geom=MultiPolygon(
            Polygon(
                (
                    (offset, offset),
                    (offset, offset + 1),
                    (offset + 1, offset + 1),
                    (offset + 1, offset),
                    (offset, offset),
                )
            )
        )
    )


class TwoVintageTestCase(TestCase):
    """DE111 exists in both NUTS 2021 (current) and NUTS 2024."""

    @classmethod
    def setUpTestData(cls):
        cls.v2021 = NutsVintage.objects.get(year=2021)
        cls.v2024 = NutsVintage.objects.create(year=2024)
        cls.country_2021 = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=cls.v2021,
        )
        cls.country_2024 = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=cls.v2024,
        )
        cls.region_2021 = NutsRegion.objects.create(
            name="Flensburg",
            nuts_id="DE111",
            levl_code=3,
            cntr_code="DE",
            parent=cls.country_2021,
            version=cls.v2021,
            borders=_borders(),
        )
        cls.region_2024 = NutsRegion.objects.create(
            name="Flensburg",
            nuts_id="DE111",
            levl_code=3,
            cntr_code="DE",
            parent=cls.country_2024,
            version=cls.v2024,
            borders=_borders(10.0),
        )


class NutsRegionGeoJSONVintageScopeTestCase(TwoVintageTestCase):
    def setUp(self):
        self.url = reverse("api-nuts-region-geojson")

    def test_geojson_returns_only_the_current_vintage(self):
        response = self.client.get(self.url, {"levl_code": 3, "cntr_code": "DE"})
        self.assertEqual(response.status_code, 200)
        features = response.json()["features"]
        self.assertEqual(len(features), 1)
        self.assertEqual(_x_origin(features[0]), 0.0)

    def test_geojson_accepts_an_explicit_vintage(self):
        response = self.client.get(
            self.url, {"levl_code": 3, "cntr_code": "DE", "version": "2024"}
        )
        self.assertEqual(response.status_code, 200)
        features = response.json()["features"]
        self.assertEqual(len(features), 1)
        self.assertEqual(_x_origin(features[0]), 10.0)

    def test_geojson_rejects_a_vintage_that_is_not_held(self):
        response = self.client.get(
            self.url, {"levl_code": 3, "cntr_code": "DE", "version": "2016"}
        )
        self.assertEqual(response.status_code, 400)

    def test_list_endpoint_is_scoped_as_well(self):
        response = self.client.get(reverse("api-nuts-region-list"), {"levl_code": 3})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        results = payload["results"] if isinstance(payload, dict) else payload
        self.assertEqual([entry["id"] for entry in results], [self.region_2021.pk])

    def test_geojson_by_id_is_not_served_from_another_requests_cache(self):
        first = self.client.get(self.url, {"id": self.region_2021.pk})
        second = self.client.get(
            self.url, {"id": self.region_2024.pk, "version": "2024"}
        )
        self.assertEqual(_x_origin(first.json()["features"][0]), 0.0)
        self.assertEqual(_x_origin(second.json()["features"][0]), 10.0)

    def test_cache_keys_for_one_region_still_differ_per_vintage(self):
        self.assertNotEqual(
            get_nuts_region_cache_key(nuts_id=4, version=2021),
            get_nuts_region_cache_key(nuts_id=4, version=2024),
        )

    def test_cache_keys_differ_per_region(self):
        self.assertNotEqual(
            get_nuts_region_cache_key(nuts_id=4, version=2021),
            get_nuts_region_cache_key(nuts_id=5, version=2021),
        )

    def test_cache_keys_differ_per_vintage(self):
        self.assertNotEqual(
            get_nuts_region_cache_key(
                level=3, filters={"cntr_code": "DE"}, version=2021
            ),
            get_nuts_region_cache_key(
                level=3, filters={"cntr_code": "DE"}, version=2024
            ),
        )


class NutsRegionHierarchyVintageScopeTestCase(TwoVintageTestCase):
    def test_pedigree_children_stay_within_the_regions_vintage(self):
        children = self.country_2024.pedigree["qs_3"]
        self.assertEqual(list(children), [self.region_2024])

    def test_pedigree_api_children_stay_within_the_regions_vintage(self):
        response = self.client.get(
            reverse("data.nuts_region_options"),
            {"id": self.country_2024.pk, "direction": "children"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [option["id"] for option in response.json()["id_level_3"]],
            [self.region_2024.pk],
        )


class NutsRegionAutocompleteVintageScopeTestCase(TwoVintageTestCase):
    def test_autocomplete_offers_each_territory_once(self):
        response = self.client.get(reverse("nutsregion-autocomplete-level3"))
        self.assertEqual(response.status_code, 200)
        ids = [result["id"] for result in response.json()["results"]]
        self.assertEqual(ids, [self.region_2021.pk])


class SetCountryVintageScopeTestCase(TwoVintageTestCase):
    def test_country_is_derived_from_the_current_vintage_only(self):
        """A level-0 region of a non-current vintage must not claim the territory."""
        for country in (self.country_2021, self.country_2024):
            country.borders = GeoPolygon.objects.create(
                geom=MultiPolygon(
                    Polygon(((-5, -5), (-5, 5), (5, 5), (5, -5), (-5, -5)))
                )
            )
            country.save()
        # Sorts first, so an unscoped lookup would pick the 2024 row.
        self.country_2024.name = "A Deutschland"
        self.country_2024.cntr_code = "XX"
        self.country_2024.save()

        region = Region.objects.create(name="Child", borders=_borders())
        self.assertEqual(region.country, "DE")
