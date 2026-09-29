from django.test import TestCase
from django.urls import reverse

PERMALINK_PREFIX = "/waste_collection/waste-atlas/p/"


class WasteAtlasPermalinkTests(TestCase):
    def test_permalink_is_addressed_by_map_set_theme_and_year(self):
        self.assertEqual(
            reverse("waste-atlas-permalink", args=["DE", "collection_system", 2024]),
            f"{PERMALINK_PREFIX}DE/collection_system/2024/",
        )

    def test_permalink_resolves_to_the_current_map_page_for_anyone(self):
        response = self.client.get(f"{PERMALINK_PREFIX}DE/collection_system/2023/")

        self.assertRedirects(
            response,
            f"{reverse('waste-atlas-germany-collection-system-map')}?year=2023",
            fetch_redirect_response=False,
        )

    def test_permalink_ignores_the_case_of_the_map_set(self):
        response = self.client.get(f"{PERMALINK_PREFIX}de-nw/collection_system/2024/")

        self.assertRedirects(
            response,
            f"{reverse('waste-atlas-nrw-collection-system-map')}?year=2024",
            fetch_redirect_response=False,
        )

    def test_permalink_never_carries_a_private_scope(self):
        response = self.client.get(
            f"{PERMALINK_PREFIX}DE/collection_system/2024/", {"scope": "all"}
        )

        self.assertNotIn("scope", response["Location"])

    def test_unknown_maps_and_years_are_not_found(self):
        for path in (
            "DE/no_such_theme/2024/",
            "XX/collection_system/2024/",
            "DE/collection_system/1999/",
            "DE/collection_system/20000/",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.get(PERMALINK_PREFIX + path).status_code, 404
                )

    def test_map_page_offers_its_absolute_permalink(self):
        response = self.client.get(
            reverse("waste-atlas-germany-collection-system-map"), {"year": "2023"}
        )

        self.assertContains(
            response,
            f"http://testserver{PERMALINK_PREFIX}DE/collection_system/2023/",
        )

    def test_change_maps_and_generic_pages_do_not_offer_a_permalink(self):
        for url in (
            reverse("waste-atlas-change-map", args=["DE", "collection_system"]),
            reverse("waste-atlas-orga-level-map"),
        ):
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), PERMALINK_PREFIX)


class WasteAtlasPermalinkRegionTests(TestCase):
    """A permalink must reproduce the region the page actually shows."""

    def test_unlocked_page_showing_another_region_offers_no_permalink(self):
        url = reverse("waste-atlas-sweden-collection-system-map")
        for query in (
            {"country": "DE"},
            {"nuts_prefix": "SE1"},
            {"nuts_level": "2"},
        ):
            with self.subTest(query=query):
                response = self.client.get(url, {"year": "2023", **query})
                self.assertEqual(response.context["atlas_permalink_url"], "")
                self.assertNotContains(response, PERMALINK_PREFIX)

    def test_unlocked_page_with_its_own_region_keeps_its_permalink(self):
        url = reverse("waste-atlas-sweden-collection-system-map")
        response = self.client.get(url, {"year": "2023", "country": "SE"})
        self.assertContains(response, f"{PERMALINK_PREFIX}SE/collection_system/2023/")

    def test_permalink_exposes_its_region_for_in_place_reloads(self):
        response = self.client.get(reverse("waste-atlas-bw-collection-system-map"))
        content = response.content.decode()
        self.assertIn(
            f'data-permalink-base="http://testserver{PERMALINK_PREFIX}DE-BW/collection_system/"',
            content,
        )
        self.assertIn('data-permalink-country="DE"', content)
        self.assertIn('data-permalink-nuts-prefix="DE1"', content)
        self.assertIn('data-permalink-years="2020,2021,2022,2023,2024"', content)
