import re
from html.parser import HTMLParser
from pathlib import Path

from django.contrib.auth.models import Permission, User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from brit.featured import BRIT_EU_MAP_LINKS, FEATURED_DESTINATIONS
from brit.sitemap_items import BASE_SITEMAP_ITEMS
from sources.waste_collection.waste_atlas.pages import MAP_PAGES

REPO_ROOT = Path(__file__).resolve().parents[2]


class FeatureParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.features = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "data-feature-slug" in attrs:
            self._current = {
                "slug": attrs["data-feature-slug"],
                "imgs": [],
                "anchors": [],
            }
            self.features.append(self._current)
        elif self._current is not None and tag == "img":
            self._current["imgs"].append(attrs)
        elif self._current is not None and tag == "a":
            self._current["anchors"].append(attrs)

    def handle_startendtag(self, tag, attrs):
        if tag == "img" and self._current is not None:
            self._current["imgs"].append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "article":
            self._current = None


class FeaturedRegistryTests(TestCase):
    def test_three_ordered_destinations_with_resolvable_routes(self):
        self.assertEqual(
            [f["slug"] for f in FEATURED_DESTINATIONS],
            ["waste-atlas", "brit-eu", "closecycle"],
        )
        for feature in FEATURED_DESTINATIONS:
            for key in (
                "slug",
                "category",
                "title",
                "description",
                "url_name",
                "cta_label",
                "image_path",
                "image_alt",
                "image_width",
                "image_height",
                "logos",
            ):
                self.assertIn(key, feature)
            self.assertTrue(reverse(feature["url_name"]))

    def test_collection_map_previews_match_featured_destinations(self):
        by_slug = {feature["slug"]: feature for feature in FEATURED_DESTINATIONS}
        expected = {
            "waste-atlas": (
                "img/featured/germany_organic_collection_amount_map.webp",
                "Map of German districts coloured by the collected amount of organic waste per capita",
            ),
            "brit-eu": (
                "img/featured/europe_data_coverage_map.webp",
                "Map of Europe highlighting the regions with biowaste collection data",
            ),
        }

        for slug, (image_path, image_alt) in expected.items():
            with self.subTest(slug=slug):
                self.assertEqual(by_slug[slug]["image_path"], image_path)
                self.assertEqual(by_slug[slug]["image_alt"], image_alt)

    def test_featured_images_are_distinct_from_module_covers(self):
        home_url = reverse("home")
        anonymous_response = self.client.get(home_url)
        self.assertEqual(anonymous_response.status_code, 200)

        for feature in FEATURED_DESTINATIONS:
            with self.subTest(slug=feature["slug"]):
                self.assertTrue(feature["image_path"].startswith("img/featured/"))
                self.assertContains(
                    anonymous_response, Path(feature["image_path"]).name
                )

        user = User.objects.create_user(username="featured-image-viewer")
        permission = Permission.objects.get(
            content_type__app_label="processes",
            codename="access_app_feature",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)
        response = self.client.get(home_url)
        self.assertEqual(response.status_code, 200)

        html = response.content.decode()
        featured_section = html[
            html.index('id="featured-results"') : html.index('id="modules"')
        ]
        modules_section = html[html.index('id="modules"') :]

        for feature in FEATURED_DESTINATIONS:
            with self.subTest(slug=feature["slug"]):
                self.assertNotIn(Path(feature["image_path"]).name, modules_section)

        for module_cover in ("maps_cover_card.png", "processes_cover_card.png"):
            with self.subTest(module_cover=module_cover):
                self.assertIn(module_cover, modules_section)
                self.assertNotIn(module_cover, featured_section)

    def test_registry_images_resolve_with_native_dimensions(self):
        from PIL import Image

        assets = [
            (f["image_path"], f["image_width"], f["image_height"])
            for f in FEATURED_DESTINATIONS
        ]
        for feature in FEATURED_DESTINATIONS:
            assets += [
                (logo["image_path"], logo["width"], logo["height"])
                for logo in feature["logos"]
            ]
        for path, width, height in assets:
            found = finders.find(path)
            self.assertIsNotNone(found, path)
            with Image.open(found) as image:
                image.verify()
            with Image.open(found) as image:
                self.assertEqual(image.size, (width, height), path)

    def test_map_links_resolve_to_collection_system_pages(self):
        self.assertEqual(len(BRIT_EU_MAP_LINKS), 5)
        pages = {p["name"]: p for p in MAP_PAGES}
        expected_sets = {
            "Catalonia": "ES-CT",
            "North Rhine-Westphalia": "DE-NW",
            "Rhineland-Palatinate": "DE-RP",
            "Sweden": "SE",
            "South Tyrol": "IT-ST",
        }
        self.assertEqual(
            [link["label"] for link in BRIT_EU_MAP_LINKS], list(expected_sets)
        )
        for link in BRIT_EU_MAP_LINKS:
            self.assertTrue(reverse(link["url_name"]))
            page = pages[link["url_name"]]
            self.assertEqual(page["theme"], "collection_system")
            self.assertEqual(page["selector_set"], expected_sets[link["label"]])
            self.assertEqual(
                page["title"], "Primary collection system for kitchen waste"
            )


class HomeFeaturedTests(TestCase):
    def _home(self):
        return self.client.get(reverse("home"))

    def _features(self, response):
        parser = FeatureParser()
        parser.feed(response.content.decode())
        return parser.features

    def test_anonymous_home_renders_hero_without_breadcrumb(self):
        response = self._home()

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(
            response, '<h1 class="sdv2-hero-title">Bioresource Information Tool</h1>'
        )
        self.assertNotContains(response, "page-breadcrumb-rail")
        self.assertNotContains(response, "News & Updates")

    def test_three_feature_articles_in_order_before_modules(self):
        response = self._home()
        html = response.content.decode()
        features = self._features(response)

        self.assertEqual(
            [f["slug"] for f in features],
            ["waste-atlas", "brit-eu", "closecycle"],
        )
        self.assertLess(
            html.index('id="featured-results"'), html.index("Browse the modules")
        )
        self.assertTemplateUsed(response, "includes/featured_destination_card.html")

        expected = {
            "waste-atlas": reverse("waste-atlas-overview"),
            "brit-eu": reverse("brit-eu-results"),
            "closecycle": reverse("Showcase"),
        }
        for feature in features:
            hrefs = [a.get("href") for a in feature["anchors"]]
            self.assertIn(expected[feature["slug"]], hrefs)

    def test_module_links_retained_and_processes_gated(self):
        response = self._home()
        for name in (
            "maps_list",
            "sample-list",
            "sources-explorer",
            "scenario-list",
            "source-list",
        ):
            self.assertContains(response, reverse(name))
        self.assertNotContains(response, reverse("processes:process-list"))

        user = User.objects.create_user(username="featured-participant")
        permission = Permission.objects.get(
            content_type__app_label="processes",
            codename="access_app_feature",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)
        self.assertContains(self._home(), reverse("processes:process-list"))

    def test_feature_logos_use_bounded_classes(self):
        features = self._features(self._home())
        by_slug = {f["slug"]: f for f in features}

        brit_eu_img = next(
            i
            for i in by_slug["brit-eu"]["imgs"]
            if i["src"].endswith("brit_eu_logo.png")
        )
        self.assertIn("discovery-logo", brit_eu_img.get("class", "").split())
        self.assertEqual(brit_eu_img["alt"], "BRIT-EU logo")
        self.assertEqual((brit_eu_img["width"], brit_eu_img["height"]), ("1335", "387"))

        closecycle_imgs = {
            i["src"].rsplit("/", 1)[-1]: i for i in by_slug["closecycle"]["imgs"]
        }
        interreg = closecycle_imgs["interreg_with_closecycle_logo.png"]
        self.assertIn("discovery-logo-interreg", interreg["class"].split())
        self.assertEqual((interreg["width"], interreg["height"]), ("1237", "500"))
        standalone = closecycle_imgs["closecycle_logo.png"]
        self.assertIn("discovery-logo-secondary", standalone["class"].split())
        self.assertEqual(standalone["alt"], "CLOSECYCLE logo")
        self.assertEqual((standalone["width"], standalone["height"]), ("506", "91"))

        self.assertEqual(len(by_slug["waste-atlas"]["imgs"]), 1)


class BritEuResultsPageTests(TestCase):
    def test_public_page_route_template_breadcrumb_sitemap(self):
        url = reverse("brit-eu-results")
        self.assertEqual(url, "/projects/brit-eu/")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "brit_eu_results.html")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">BRIT-EU results</li>',
            html=True,
        )
        self.assertIn("/projects/brit-eu/", BASE_SITEMAP_ITEMS)

    def test_five_curated_map_links_scoped_to_maps_section(self):
        response = self.client.get(reverse("brit-eu-results"))
        html = response.content.decode()

        section = html[
            html.index('id="brit-eu-maps"') : html.index('id="data-analysis"')
        ]
        for link in BRIT_EU_MAP_LINKS:
            self.assertIn(link["label"], section)
            self.assertIn(reverse(link["url_name"]), section)
        self.assertEqual(
            section.count("Primary collection system for kitchen waste"), 5
        )
        self.assertIn("Open map", section)

    def test_map_destinations_resolve_anonymously(self):
        for link in BRIT_EU_MAP_LINKS:
            response = self.client.get(reverse(link["url_name"]))
            self.assertEqual(response.status_code, 200, link["url_name"])

    def test_distinguishes_atlas_and_analysis_access(self):
        response = self.client.get(reverse("brit-eu-results"))

        self.assertContains(
            response,
            "BRIT-EU maps are part of the Waste Atlas, which also includes maps "
            "beyond this project.",
        )
        self.assertContains(response, reverse("waste-atlas-overview"))
        self.assertContains(response, reverse("collection-list"))
        self.assertContains(response, reverse("r-analysis"))
        self.assertContains(response, "analysis_api")
        self.assertContains(response, "archived")
        self.assertContains(response, "#project-history")

    def test_discovery_css_bounds_covers_logos_and_cta(self):
        css_path = finders.find("css/discovery.css")
        self.assertIsNotNone(css_path, "discovery.css source not found")
        css = Path(css_path).read_text()

        cover = re.search(
            r"\.discovery-page \.discovery-feature-cover\s*\{([^}]*)\}", css
        )
        self.assertIsNotNone(cover)
        for fragment in (
            "position: relative",
            "aspect-ratio: 16 / 9",
            "flex-shrink: 0",
            "max-height: 11rem",
        ):
            self.assertIn(fragment, cover.group(1))
        cover_img = re.search(
            r"\.discovery-page \.discovery-feature-cover img\s*\{([^}]*)\}", css
        )
        self.assertIsNotNone(cover_img)
        for fragment in ("position: absolute", "object-fit: contain"):
            self.assertIn(fragment, cover_img.group(1))

        interreg = re.search(
            r"\.discovery-page \.discovery-logo-interreg\s*\{([^}]*)\}", css
        )
        self.assertIsNotNone(interreg)
        interreg_declarations = {
            declaration.strip()
            for declaration in interreg.group(1).split(";")
            if declaration.strip()
        }
        for declaration in ("width: auto", "max-width: 100%", "max-height: 5rem"):
            self.assertIn(declaration, interreg_declarations)
        self.assertNotIn("width: 100%", interreg_declarations)
        secondary = re.search(
            r"\.discovery-page \.discovery-logo-secondary\s*\{([^}]*)\}", css
        )
        self.assertIsNotNone(secondary)
        self.assertIn("max-width: 6rem", secondary.group(1))
        self.assertIn("max-height: 2rem", secondary.group(1))

        cta = re.search(r"\.discovery-page a\.discovery-feature-cta\s*\{([^}]*)\}", css)
        self.assertIsNotNone(cta, "CTA selector must outrank shared sdv2 anchor rule")
        self.assertIn("margin-top: auto", cta.group(1))

        self.assertIsNotNone(
            finders.find("css/discovery.min.css"),
            "discovery.min.css build artifact missing",
        )

    def test_template_does_not_embed_archive_download_details(self):
        source = (REPO_ROOT / "brit/templates/brit_eu_results.html").read_text()

        self.assertNotIn("BRIT-EU-R", source)
        self.assertNotIn(".zip", source)
        self.assertNotIn("amazonaws", source)
