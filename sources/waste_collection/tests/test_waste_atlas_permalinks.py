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
