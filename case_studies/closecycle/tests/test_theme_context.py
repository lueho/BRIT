from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from maps.models import (
    Catchment,
    GeoDataset,
    MapConfiguration,
    MapLayerConfiguration,
    Region,
)

from ..filters import ShowcaseFilterSet
from ..models import Showcase
from ..serializers import ShowcaseFlatSerializer
from ..themes import get_theme, pilot_region_info


class ShowcaseThemeContextTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="theme_owner")
        cls.region = Region.objects.create(
            name="Administrative context", country="FR", publication_status="published"
        )
        cls.region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)))
        cls.region.save()
        cls.pilot = Catchment.objects.create(
            name="Example regional network",
            description="Growers, processors and product users exchange regional residues.",
            region=cls.region,
            publication_status="published",
        )
        cls.showcase = Showcase.objects.create(
            name="A demonstration site",
            region=cls.region,
            catchment=cls.pilot,
            geom=Point(1, 2, srid=4326),
            publication_status="published",
        )
        GeoDataset.objects.create(
            name="Showcase theme test", model_name="Showcase", region=cls.region
        )
        config, _ = MapConfiguration.objects.get_or_create(
            name="Default Map Configuration"
        )
        for kind in ("region", "catchment", "features"):
            layer = MapLayerConfiguration.objects.create(
                name=f"Theme test {kind}", layer_type=kind
            )
            config.layers.add(layer)

    def assign_theme(self, theme="apple_chain"):
        Showcase.objects.filter(pk=self.showcase.pk).update(theme=theme)
        self.showcase.refresh_from_db()

    def test_theme_is_explicit_and_validated(self):
        field = Showcase._meta.get_field("theme")
        self.assertEqual(7, len(field.choices))
        self.assertTrue(field.blank)
        with self.assertRaises(ValidationError):
            field.clean("not_a_theme", self.showcase)
        self.assign_theme()
        self.assertEqual("apple_chain", Showcase.objects.get(pk=self.showcase.pk).theme)

    def test_summary_exposes_theme_and_visible_pilot_context(self):
        self.assign_theme()
        data = ShowcaseFlatSerializer(self.showcase).data
        self.assertEqual("Apple Chain", data["theme"]["label"])
        self.assertEqual("#ff4f4f", data["theme"]["color"])
        self.assertEqual(self.pilot.pk, data["pilot_region"]["id"])
        self.assertEqual(self.pilot.description, data["pilot_region"]["description"])
        self.assertIn("stakeholders", data["pilot_region"]["role"])
        self.assertIn("boundaries", data["pilot_region"]["boundary_note"])
        self.assertEqual(
            reverse("catchment-detail", args=[self.pilot.pk]),
            data["pilot_region"]["url"],
        )

    def test_database_default_supports_writers_from_before_the_theme_migration(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO closecycle_showcase (name, owner_id, publication_status, created_at, lastmodified_at) "
                "VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING theme",
                ["Older writer compatibility", self.owner.pk, "published"],
            )
            self.assertEqual("", cursor.fetchone()[0])

    def test_unknown_theme_has_no_inferred_assignment(self):
        data = ShowcaseFlatSerializer(self.showcase).data
        self.assertIsNone(data["theme"])

    def test_private_pilot_context_is_hidden_but_owner_can_read_it(self):
        self.pilot.publication_status = "private"
        self.pilot.owner = self.owner
        self.pilot.save()
        self.assertIsNone(ShowcaseFlatSerializer(self.showcase).data["pilot_region"])
        owner_context = {"request": SimpleNamespace(user=self.owner)}
        data = ShowcaseFlatSerializer(self.showcase, context=owner_context).data
        self.assertEqual(self.pilot.pk, data["pilot_region"]["id"])

    def test_polygon_contains_context_and_only_visible_themes(self):
        self.assign_theme()
        Showcase.objects.create(
            name="Hidden other theme",
            theme="greenhouses",
            catchment=self.pilot,
            owner=self.owner,
        )
        data = self.client.get(reverse("api-showcase-geojson")).json()
        pilot = next(
            f
            for f in data["features"]
            if f["properties"]["feature_type"] == "pilot_region"
        )
        self.assertEqual(
            self.pilot.description, pilot["properties"]["pilot_region"]["description"]
        )
        self.assertEqual("apple_chain", pilot["properties"]["theme"]["key"])
        self.assertEqual(
            ["apple_chain"], [t["key"] for t in pilot["properties"]["themes"]]
        )
        point = next(f for f in data["features"] if f["id"] == self.showcase.pk)
        self.assertEqual("Apple Chain", point["properties"]["theme"]["label"])

    def test_theme_and_pilot_filters_apply_to_both_geometries_and_summaries(self):
        self.assign_theme()
        Showcase.objects.create(
            name="Other theme",
            theme="greenhouses",
            region=self.region,
            catchment=self.pilot,
            publication_status="published",
        )
        params = {"theme": "apple_chain", "pilot_region": self.pilot.pk}
        data = self.client.get(reverse("api-showcase-geojson"), params).json()
        points = [
            f["id"]
            for f in data["features"]
            if f["properties"]["feature_type"] == "showcase"
        ]
        self.assertEqual([self.showcase.pk], points)
        pilot = next(
            f
            for f in data["features"]
            if f["properties"]["feature_type"] == "pilot_region"
        )
        self.assertEqual(
            [self.showcase.pk], [s["id"] for s in pilot["properties"]["showcases"]]
        )
        summaries = self.client.get(reverse("api-showcase-summaries"), params).json()
        self.assertEqual([self.showcase.pk], [s["id"] for s in summaries["summaries"]])

    def test_api_preserves_legacy_country_filter_and_rejects_invalid_theme(self):
        self.assign_theme()
        response = self.client.get(
            reverse("api-showcase-summaries"), {"region__country": "DE"}
        )
        self.assertEqual([], response.json()["summaries"])
        response = self.client.get(
            reverse("api-showcase-geojson"), {"theme": "not_a_theme"}
        )
        self.assertEqual(400, response.status_code)

    def test_pilot_filter_choices_hide_private_catchments(self):
        private = Catchment.objects.create(
            name="Secret network", region=self.region, owner=self.owner
        )
        Showcase.objects.create(
            name="Public site, private network",
            catchment=private,
            publication_status="published",
        )
        request = RequestFactory().get("/")
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        filters = ShowcaseFilterSet(queryset=Showcase.objects.all(), request=request)
        choices = filters.filters["pilot_region"].queryset
        self.assertIn(self.pilot.pk, choices.values_list("pk", flat=True))
        self.assertNotIn(private.pk, choices.values_list("pk", flat=True))

    def test_theme_edit_without_timestamp_change_rotates_geojson_version(self):
        before = self.client.get(reverse("api-showcase-version")).json()["version"]
        self.assign_theme()
        after = self.client.get(reverse("api-showcase-version")).json()["version"]
        self.assertNotEqual(before, after)

    def test_map_has_theme_legend_filters_and_region_explanation(self):
        self.assign_theme()
        response = self.client.get(
            reverse("Showcase"), {"scope": "published", "theme": "apple_chain"}
        )
        self.assertEqual(200, response.status_code)
        for text in (
            "Apple Chain",
            "Biorefinery Modules",
            "Territorial Biorefinery Network",
            "administrative boundaries",
            'id="pilot-region-context"',
            'name="theme"',
            'name="pilot_region"',
        ):
            self.assertContains(response, text)

    def test_map_filter_form_and_links_keep_published_scope(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("Showcase"), {"scope": "published", "theme": "apple_chain"}
        )
        self.assertContains(
            response, '<input type="hidden" name="scope" value="published">', html=True
        )
        theme_url = get_theme("apple_chain")["url"]
        self.assertEqual(
            {"published"}, set(parse_qs(urlsplit(theme_url).query)["scope"])
        )
        showcases_url = pilot_region_info(self.pilot)["showcases_url"]
        query = parse_qs(urlsplit(showcases_url).query)
        self.assertEqual(["published"], query["scope"])
        self.assertEqual([str(self.pilot.pk)], query["pilot_region"])

    def test_map_filter_button_keeps_filters_in_the_address_bar(self):
        response = self.client.get(reverse("Showcase"), {"scope": "published"})
        # maps.js reads the filters from the form of the ``.submit-filter``
        # button when it rewrites the address bar after loading.
        self.assertContains(
            response,
            '<button class="btn btn-sm btn-primary submit-filter" type="submit">'
            "Filter</button>",
            html=True,
        )

    def _panel_showcase(self, name, country, region_status="published", **kwargs):
        region = Region.objects.create(
            name=f"{name} region", country=country, publication_status=region_status
        )
        return Showcase.objects.create(
            name=name,
            region=region,
            geom=Point(14, 58, srid=4326),
            publication_status=kwargs.pop("publication_status", "published"),
            owner=self.owner,
            **kwargs,
        )

    def test_map_panel_lists_published_showcases_by_country_and_code(self):
        sc14 = self._panel_showcase("SC14 \u2013 Grass to protein", "SE")
        sc2 = self._panel_showcase("SC2 \u2013 Biogas", "SE")
        hidden = self._panel_showcase(
            "SC99 \u2013 Unpublished", "SE", publication_status="private"
        )
        response = self.client.get(reverse("Showcase"), {"scope": "published"})
        self.assertContains(response, 'id="showcase-list"')
        self.assertContains(response, f'data-showcase-id="{sc14.pk}"')
        self.assertContains(response, f'data-showcase-id="{self.showcase.pk}"')
        self.assertNotContains(response, f'data-showcase-id="{hidden.pk}"')
        self.assertNotContains(response, "Unpublished")
        self.assertContains(response, '<span class="csm-code">SC14</span>', html=True)
        self.assertContains(response, "3 showcases in 2 countries")
        content = response.content.decode()
        list_start = content.index('id="showcase-list"')
        self.assertLess(
            content.index("France", list_start), content.index("Sweden", list_start)
        )
        self.assertLess(
            content.index(f'data-showcase-id="{sc2.pk}"'),
            content.index(f'data-showcase-id="{sc14.pk}"'),
        )

    def test_map_panel_does_not_reveal_the_country_of_a_private_region(self):
        showcase = self._panel_showcase(
            "SC5 \u2013 Private region", "SE", region_status="private"
        )
        response = self.client.get(reverse("Showcase"), {"scope": "published"})
        content = response.content.decode()
        listing = content[content.index('id="showcase-list"') :]
        self.assertIn(f'data-showcase-id="{showcase.pk}"', listing)
        self.assertIn("Other", listing)
        self.assertNotIn("Sweden", listing)

    def test_country_filter_defaults_to_all_countries(self):
        choices = list(ShowcaseFilterSet().form.fields["country"].widget.choices)
        self.assertEqual(("", "All countries"), choices[0])

    def test_map_panel_list_follows_the_filters(self):
        self.assign_theme()
        other = self._panel_showcase("SC3 \u2013 Other theme", "SE")
        response = self.client.get(
            reverse("Showcase"), {"scope": "published", "theme": "apple_chain"}
        )
        self.assertContains(response, f'data-showcase-id="{self.showcase.pk}"')
        self.assertNotContains(response, f'data-showcase-id="{other.pk}"')
        self.assertContains(response, "1 showcase in 1 country")

    def test_map_without_scope_redirects_to_published_scope(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("Showcase"), {"theme": "apple_chain", "pilot_region": self.pilot.pk}
        )
        self.assertEqual(302, response.status_code)
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(["published"], query["scope"])
        self.assertEqual(["apple_chain"], query["theme"])
        self.assertEqual([str(self.pilot.pk)], query["pilot_region"])

    def test_detail_page_explains_theme_and_network_without_calling_it_catchment(self):
        self.assign_theme()
        response = self.client.get(reverse("showcase-detail", args=[self.showcase.pk]))
        self.assertContains(response, "Apple Chain")
        self.assertContains(response, "Pilot region")
        self.assertContains(response, "Territorial Biorefinery Network")
        self.assertContains(response, self.pilot.description)
        self.assertNotContains(response, "<strong>Catchment:</strong>", html=False)
        self.assertContains(response, "Explore regional showcases")

    def test_shared_pilot_with_multiple_themes_uses_neutral_polygon_colour(self):
        self.assign_theme()
        Showcase.objects.create(
            name="Other theme",
            theme="greenhouses",
            catchment=self.pilot,
            publication_status="published",
        )
        features = self.client.get(reverse("api-showcase-geojson")).json()["features"]
        pilot = next(
            f for f in features if f["properties"]["feature_type"] == "pilot_region"
        )
        self.assertIsNone(pilot["properties"]["theme"])
        self.assertEqual(
            {"apple_chain", "greenhouses"},
            {t["key"] for t in pilot["properties"]["themes"]},
        )

    def test_private_pilot_selection_is_rejected_without_exposing_details(self):
        private = Catchment.objects.create(
            name="Invisible network", region=self.region, owner=self.owner
        )
        response = self.client.get(
            reverse("api-showcase-summaries"), {"pilot_region": private.pk}
        )
        self.assertEqual(400, response.status_code)
        self.assertNotContains(response, "Invisible network", status_code=400)

    def test_summary_pilot_context_queries_do_not_grow_per_catchment(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def query_count():
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse("api-showcase-summaries"))
            self.assertEqual(200, response.status_code)
            return len(queries)

        before = query_count()
        for index in range(3):
            pilot = Catchment.objects.create(
                name=f"Additional network {index}",
                region=self.region,
                publication_status="published",
            )
            Showcase.objects.create(
                name=f"Additional site {index}",
                catchment=pilot,
                publication_status="published",
            )
        self.assertEqual(before, query_count())
