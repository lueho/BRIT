"""The Waste Atlas dashboard summarises the atlas maps as interactive charts.

The atlas answers "where" for one theme at a time. The dashboard answers "how
much" for a whole region: every map page of a region contributes one chart of
its own value distribution, built from the very same API endpoint and stored
map configuration the choropleth renders, so a chart can never show a different
classification or palette than its map.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.waste_atlas.map_configs import MAP_CONFIGS
from sources.waste_collection.waste_atlas.map_selection import (
    DIRECTORY_SECTION_ORDER,
    MAP_SELECTION_YEARS,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES

DASHBOARD_ROUTE = "waste-atlas-dashboard"


def _chartable_themes(map_set):
    """Return the themes of a map set whose stored config can drive a chart."""
    configs = dict(MAP_CONFIGS.items())
    return {
        page["theme"]
        for page in MAP_PAGES
        if page["selector_set"] == map_set
        and configs.get(page["config_key"], {}).get("dataUrl")
        and configs.get(page["config_key"], {}).get("categories")
    }


class WasteAtlasDashboardAccessTests(TestCase):
    """The dashboard is scoped to the atlas group, like every atlas page."""

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.member = User.objects.create_user(
            username="dashboard-member", password="secret"
        )
        cls.member.groups.add(group)
        cls.outsider = User.objects.create_user(
            username="dashboard-outsider", password="secret"
        )

    def test_anonymous_users_are_redirected_to_the_login(self):
        response = self.client.get(reverse(DASHBOARD_ROUTE))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_users_outside_the_atlas_group_are_rejected(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse(DASHBOARD_ROUTE))

        self.assertEqual(response.status_code, 403)

    def test_group_members_get_the_dashboard(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse(DASHBOARD_ROUTE))

        self.assertEqual(response.status_code, 200)


class WasteAtlasDashboardContentTests(TestCase):
    """Every chart is generated from the map registry and its stored config."""

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user = User.objects.create_user(
            username="dashboard-user", password="secret"
        )
        cls.user.groups.add(group)

    def setUp(self):
        self.client.force_login(self.user)

    def _dashboard(self, query=""):
        response = self.client.get(f"{reverse(DASHBOARD_ROUTE)}{query}")
        self.assertEqual(response.status_code, 200)
        return response

    def _config(self, query=""):
        return self._dashboard(query).context["dashboard_config"]

    def test_charts_cover_every_map_of_the_selected_region(self):
        config = self._config("?region=IT-ST")

        charted = {panel["theme"] for panel in config["panels"]}
        self.assertEqual(charted, _chartable_themes("IT-ST"))
        self.assertGreater(len(charted), 5)

    def test_each_chart_reuses_the_data_source_of_its_map(self):
        config = self._config("?region=DE")

        panel = next(
            panel for panel in config["panels"] if panel["theme"] == "collection_system"
        )
        stored = MAP_CONFIGS["collection_system"]
        self.assertEqual(panel["dataUrl"], stored["dataUrl"])
        self.assertEqual(panel["dataField"], stored["dataField"])
        self.assertEqual(
            [category["color"] for category in panel["categories"]],
            [category["color"] for category in stored["categories"]],
        )
        self.assertEqual(
            panel["mapUrl"],
            reverse("waste-atlas-germany-collection-system-map"),
        )

    def test_region_scope_is_passed_to_the_chart_requests(self):
        config = self._config("?region=DE-NW")

        self.assertEqual(config["country"], "DE")
        self.assertEqual(config["nutsPrefix"], "DEA")

    def test_numeric_maps_expose_their_value_field_for_a_distribution_chart(self):
        config = self._config("?region=IT")

        panel = next(
            panel
            for panel in config["panels"]
            if panel["theme"] == "residual_collection_amount"
        )
        self.assertEqual(
            panel["numericField"],
            MAP_CONFIGS["residual_collection_amount"]["numericField"],
        )
        self.assertEqual(
            panel["transformName"],
            MAP_CONFIGS["residual_collection_amount"]["transformName"],
        )

    def test_the_year_can_be_switched_and_is_offered_for_trends(self):
        config = self._config("?region=DE&year=2022")

        self.assertEqual(config["year"], 2022)
        self.assertEqual(config["years"], [int(y) for y in MAP_SELECTION_YEARS])

    def test_unknown_region_and_year_fall_back_to_the_defaults(self):
        config = self._config("?region=nowhere&year=1999")

        self.assertEqual(config["mapSet"], "DE")
        self.assertEqual(config["year"], int(MAP_SELECTION_YEARS[-1]))

    def test_charts_are_grouped_in_the_directory_section_order(self):
        response = self._dashboard("?region=IT-ST")

        sections = [
            section["key"] for section in response.context["dashboard_sections"]
        ]
        self.assertEqual(
            sections,
            [key for key in DIRECTORY_SECTION_ORDER if key in sections],
        )
        self.assertGreater(len(sections), 1)

    def test_page_offers_the_region_year_and_waste_category_selectors(self):
        content = self._dashboard().content.decode()

        self.assertIn('id="dashboard-region"', content)
        self.assertIn('id="dashboard-year"', content)
        self.assertIn('id="dashboard-category"', content)

    def test_page_loads_the_dashboard_chart_script_with_its_config(self):
        content = self._dashboard().content.decode()

        self.assertIn("waste_atlas_dashboard.min.js", content)
        self.assertIn("WasteAtlasDashboard.init(", content)
        self.assertIn('id="dashboard-config"', content)

    def test_every_chart_has_a_container_on_the_page(self):
        response = self._dashboard()
        content = response.content.decode()

        for panel in response.context["dashboard_config"]["panels"]:
            self.assertIn(f'id="{panel["chartId"]}"', content)

    def test_map_overview_links_to_the_dashboard(self):
        response = self.client.get(reverse("waste-atlas-overview"))

        self.assertContains(response, reverse(DASHBOARD_ROUTE))


class HomepageDashboardLinkTests(TestCase):
    """The dashboard is the atlas entry point advertised on the start page."""

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.member = User.objects.create_user(username="home-member", password="secret")
        cls.member.groups.add(group)
        cls.outsider = User.objects.create_user(
            username="home-outsider", password="secret"
        )

    def test_atlas_group_members_see_the_dashboard_link(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse(DASHBOARD_ROUTE))

    def test_others_do_not_see_the_dashboard_link(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, reverse(DASHBOARD_ROUTE))
