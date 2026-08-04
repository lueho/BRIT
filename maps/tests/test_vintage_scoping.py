"""User-facing NUTS queries must show one vintage, not every vintage at once."""

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import RequestFactory, TestCase
from django.urls import reverse

from ..filters import NutsRegionFilterSet
from ..models import (
    GeoDataset,
    GeoPolygon,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    NutsRegion,
    NutsVintage,
    Region,
)
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
    """DE111 exists in both NUTS 2021 (current) and NUTS 2024.

    Reference regions are published, as the import API publishes everything it
    writes; an unpublished one is a region still being worked on.
    """

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
            publication_status=NutsRegion.STATUS_PUBLISHED,
        )
        cls.country_2024 = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=cls.v2024,
            publication_status=NutsRegion.STATUS_PUBLISHED,
        )
        cls.region_2021 = NutsRegion.objects.create(
            name="Flensburg",
            nuts_id="DE111",
            levl_code=3,
            cntr_code="DE",
            parent=cls.country_2021,
            version=cls.v2021,
            borders=_borders(),
            publication_status=NutsRegion.STATUS_PUBLISHED,
        )
        cls.region_2024 = NutsRegion.objects.create(
            name="Flensburg",
            nuts_id="DE111",
            levl_code=3,
            cntr_code="DE",
            parent=cls.country_2024,
            version=cls.v2024,
            borders=_borders(10.0),
            publication_status=NutsRegion.STATUS_PUBLISHED,
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


class NutsRegionMapFilterVintageTestCase(TwoVintageTestCase):
    """The NUTS map lets a visitor pick the vintage and draws only that one."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        style = MapLayerStyle.objects.create(name="default")
        layer = MapLayerConfiguration.objects.create(
            name="default", layer_type="features", style=style
        )
        map_config = MapConfiguration.objects.create(name="default")
        map_config.layers.add(layer)
        GeoDataset.objects.create(
            name="NUTS",
            region=Region.objects.create(name="Test Region"),
            model_name="NutsRegion",
            map_configuration=map_config,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def _filterset(self, data=None):
        data = data or {}
        request = self.factory.get(reverse("NutsRegion"), data)
        return NutsRegionFilterSet(
            data=data, queryset=NutsRegion.objects.all(), request=request
        )

    def test_version_choices_are_the_held_vintages_newest_first(self):
        field = self._filterset().form.fields["version"]
        self.assertEqual(
            [value for value, _label in field.choices if value], ["2024", "2021"]
        )

    def test_version_defaults_to_the_current_vintage(self):
        self.assertEqual(self._filterset().form.fields["version"].initial, "2021")

    def test_the_selector_shows_the_vintage_the_map_draws(self):
        """The bound form would otherwise display the newest choice, 2024."""
        self.assertEqual(self._filterset().form["version"].value(), "2021")

    def test_unfiltered_map_shows_each_territory_once(self):
        self.assertEqual(
            list(self._filterset().qs.order_by("nuts_id")),
            [self.country_2021, self.region_2021],
        )

    def test_an_unbound_filterset_shows_each_territory_once(self):
        """A bare page load passes ``data=None``, which used to skip scoping."""
        filterset = NutsRegionFilterSet(
            data=None,
            queryset=NutsRegion.objects.all(),
            request=self.factory.get(reverse("NutsRegion")),
        )
        self.assertEqual(
            list(filterset.qs.order_by("nuts_id")),
            [self.country_2021, self.region_2021],
        )

    def test_one_vintage_is_shown_even_with_none_marked_current(self):
        """Without a current vintage the map must still not draw two editions."""
        NutsVintage.objects.filter(is_current=True).update(is_current=False)
        filterset = NutsRegionFilterSet(
            data=None,
            queryset=NutsRegion.objects.all(),
            request=self.factory.get(reverse("NutsRegion")),
        )
        self.assertEqual(
            list(filterset.qs.order_by("nuts_id")),
            [self.country_2024, self.region_2024],
        )

    def test_selected_vintage_replaces_the_current_one(self):
        filterset = self._filterset({"version": "2024"})
        self.assertEqual(
            list(filterset.qs.order_by("nuts_id")),
            [self.country_2024, self.region_2024],
        )

    def test_level_pickers_follow_the_selected_vintage(self):
        form = self._filterset({"version": "2024"}).form
        self.assertEqual(list(form.fields["level_0"].queryset), [self.country_2024])
        self.assertEqual(list(form.fields["level_3"].queryset), [self.region_2024])

    def test_the_map_page_renders_a_vintage_selector(self):
        response = self.client.get(reverse("NutsRegion"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="version"')
        self.assertContains(response, "NUTS 2024")

    def test_an_unheld_vintage_is_rejected(self):
        filterset = self._filterset({"version": "2016"})
        self.assertFalse(filterset.form.is_valid())
        self.assertIn("version", filterset.form.errors)


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

    def test_autocomplete_follows_an_explicitly_requested_vintage(self):
        response = self.client.get(
            reverse("nutsregion-autocomplete-level3"), {"version": "2024"}
        )
        self.assertEqual(response.status_code, 200)
        ids = [result["id"] for result in response.json()["results"]]
        self.assertEqual(ids, [self.region_2024.pk])

    def test_autocomplete_keeps_an_unpublished_region_out_of_sight(self):
        """Vintage scoping must not cost the picker its visibility filtering."""
        self.region_2021.publication_status = NutsRegion.STATUS_PRIVATE
        self.region_2021.save(update_fields=["publication_status"])

        response = self.client.get(reverse("nutsregion-autocomplete-level3"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])


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


class NutsConsumerVintageTestCase(TwoVintageTestCase):
    """Consumers a visitor reaches once BRIT holds more than one vintage."""

    def test_a_region_detail_is_served_whatever_vintage_it_belongs_to(self):
        """A primary key names one row, so scoping it to a vintage only 404s."""
        for region in (self.region_2021, self.region_2024):
            response = self.client.get(
                reverse("api-nuts-region-detail", kwargs={"pk": region.pk})
            )
            self.assertEqual(response.status_code, 200, region.version)
            self.assertEqual(response.json()["id"], region.pk)

    def test_the_nuts_picker_narrows_options_by_what_was_typed(self):
        response = self.client.get(
            reverse("nutsregion-autocomplete"), {"q": "Flensburg"}
        )
        results = response.json()["results"]
        self.assertEqual([entry["nuts_id"] for entry in results], ["DE111"])

    def test_the_nuts_picker_also_searches_by_code(self):
        response = self.client.get(reverse("nutsregion-autocomplete"), {"q": "DE111"})
        self.assertEqual(
            [entry["nuts_id"] for entry in response.json()["results"]], ["DE111"]
        )

    def _publish(self, *regions):
        Region.objects.filter(pk__in=[region.pk for region in regions]).update(
            publication_status=Region.STATUS_PUBLISHED
        )

    def test_the_generic_region_picker_offers_each_territory_once(self):
        """Regions of other vintages are the same territory under another code."""
        self._publish(self.region_2021, self.region_2024)
        response = self.client.get(reverse("region-autocomplete"), {"q": "Flensburg"})
        results = response.json()["results"]
        self.assertEqual([entry["id"] for entry in results], [self.region_2021.pk])

    def test_the_generic_region_picker_keeps_regions_that_are_not_nuts(self):
        custom = Region.objects.create(name="Flensburg harbour")
        self._publish(custom)
        response = self.client.get(reverse("region-autocomplete"), {"q": "Flensburg"})
        self.assertIn(custom.pk, [entry["id"] for entry in response.json()["results"]])
