import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

REPO_ROOT = Path(__file__).resolve().parents[2]

HISTORY_LOGOS = {
    "img/brit_eu_logo.png": (
        "BRIT-EU logo",
        "https://www.compostnetwork.info/brit-eu/",
        "1335",
        "387",
    ),
    "img/interreg_with_closecycle_logo.png": (
        "CLOSECYCLE project logo with Interreg North Sea "
        "and European Union co-funding acknowledgement",
        "https://www.interregnorthsea.eu/closecycle",
        "1237",
        "500",
    ),
    "img/interreg_with_soilcom_logo.png": (
        "SOILCOM project logo with Interreg North Sea Region "
        "and European Regional Development Fund acknowledgement",
        "https://northsearegion.eu/soilcom/",
        "571",
        "236",
    ),
    "img/closecycle_logo.png": (
        "CLOSECYCLE logo",
        "https://www.interregnorthsea.eu/closecycle",
        "506",
        "91",
    ),
    "img/soilcom_logo.png": (
        "SOILCOM logo",
        "https://northsearegion.eu/soilcom/",
        "520",
        "130",
    ),
    "img/LOGO_Flexibi_Farbe.png": (
        "FLEXIBI logo",
        "https://www.flexibi-biorefineries.eu",
        "719",
        "319",
    ),
}

FUNDING_LOGOS = {
    "img/bmftr_logo.png": (
        "German Federal Ministry of Research, Technology and Space funding acknowledgement",
        "https://www.bmftr.bund.de/DE/Home/home_node.html",
        "506",
        "338",
    ),
    "img/interreg_north_sea_logo.svg": (
        "Interreg North Sea programme logo",
        "https://www.interregnorthsea.eu/",
        "508",
        "66",
    ),
    "img/bmbf-logo.svg": (
        "German Federal Ministry of Education and Research logo",
        "https://www.bmbf.de/EN/Home/home_node.html",
        "168",
        "84",
    ),
}

BANNED_LOGOS = (
    "brit_eu_funding_logo.png",
    "interreg_with_soilcom_logo_300.png",
    "interreg_logo.png",
    "facce-logo.png",
)

INTERREG_PROJECT_LOGOS = (
    "img/interreg_with_closecycle_logo.png",
    "img/interreg_with_soilcom_logo.png",
)

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class AboutPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h3_texts = []
        self.images = []
        self.anchors = []
        self.sections = []
        self.main_count = 0
        self._stack = []
        self._link_stack = []
        self._in_h3 = False
        self._h3_buffer = []
        self._text = {
            "project-history": [],
            "project-funding": [],
            "project-contact": [],
        }

    @property
    def _scope(self):
        for _tag, scope, _about in reversed(self._stack):
            if scope:
                return scope
        return None

    def _push(self, tag, attrs):
        marker = attrs.get("id") or (
            "brit-about" if "brit-about" in attrs.get("class", "").split() else None
        )
        in_about = "brit-about" in attrs.get("class", "").split() or bool(
            self._stack and self._stack[-1][2]
        )
        self._stack.append((tag, marker, bool(in_about)))

    def _record_image(self, attrs):
        self.images.append(
            {
                "src": attrs.get("src", ""),
                "alt": attrs.get("alt", ""),
                "width": attrs.get("width"),
                "height": attrs.get("height"),
                "class": attrs.get("class", ""),
                "href": self._link_stack[-1]["href"] if self._link_stack else None,
                "link_class": (
                    self._link_stack[-1]["class"] if self._link_stack else ""
                ),
                "scope": self._scope,
                "in_about": any(frame[2] for frame in self._stack),
            }
        )

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self._record_image(attrs)
            return
        if tag == "a":
            self._link_stack.append(
                {"href": attrs.get("href"), "class": attrs.get("class", "")}
            )
            self.anchors.append({"href": attrs.get("href"), "scope": self._scope})
        elif tag in ("section", "article", "aside"):
            self.sections.append(attrs)
        elif tag == "main":
            self.main_count += 1
        elif tag == "h3" and self._scope == "project-history":
            self._in_h3 = True
            self._h3_buffer = []
        if tag not in VOID_TAGS:
            self._push(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        if tag == "img":
            self._record_image(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "a" and self._link_stack:
            self._link_stack.pop()
        if tag == "h3" and self._in_h3:
            self.h3_texts.append("".join(self._h3_buffer).strip())
            self._in_h3 = False
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        scope = self._scope
        if scope in self._text:
            self._text[scope].append(data)
        if self._in_h3:
            self._h3_buffer.append(data)

    def scoped_images(self, scope):
        return [img for img in self.images if img["scope"] == scope]

    def scoped_text(self, scope):
        return " ".join("".join(self._text[scope]).split())


class AboutProjectHistoryTests(TestCase):
    def _parsed_about(self):
        response = self.client.get(reverse("about"))
        parser = AboutPageParser()
        parser.feed(response.content.decode())
        return response, parser

    def test_about_page_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "about.html")

    def test_history_lists_projects_newest_first(self):
        _, parser = self._parsed_about()

        self.assertEqual(
            parser.h3_texts, ["BRIT-EU", "CLOSECYCLE", "SOILCOM", "FLEXIBI"]
        )

    def test_history_describes_brit_eu(self):
        _, parser = self._parsed_about()
        text = parser.scoped_text("project-history")

        for expected in (
            "December 2024 to May 2026",
            "Hamburg University of Technology",
            "European Compost Network",
            "Waste Atlas",
            "submission and review",
        ):
            self.assertIn(expected, text)

    def test_history_describes_closecycle(self):
        _, parser = self._parsed_about()
        text = parser.scoped_text("project-history")

        for expected in (
            "2024 to 2027",
            "Interreg North Sea",
            "Territorial Biorefinery Networks",
            "Materials",
            "Processes",
        ):
            self.assertIn(expected, text)

    def test_history_contains_exactly_the_six_project_logos(self):
        _, parser = self._parsed_about()

        logos = parser.scoped_images("project-history")
        self.assertEqual(len(logos), 6, logos)
        by_src = {}
        for img in logos:
            src_key = next((k for k in HISTORY_LOGOS if img["src"].endswith(k)), None)
            self.assertIsNotNone(src_key, f"unexpected History image {img['src']}")
            by_src[src_key] = img
        self.assertEqual(set(by_src), set(HISTORY_LOGOS))
        for src, (alt, href, width, height) in HISTORY_LOGOS.items():
            img = by_src[src]
            self.assertEqual(img["href"], href, src)
            self.assertEqual(img["alt"], alt, src)
            self.assertEqual((img["width"], img["height"]), (width, height), src)

    def test_funding_contains_exactly_the_three_funder_logos(self):
        _, parser = self._parsed_about()

        logos = parser.scoped_images("project-funding")
        self.assertEqual(len(logos), 3, logos)
        by_src = {}
        for img in logos:
            src_key = next((k for k in FUNDING_LOGOS if img["src"].endswith(k)), None)
            self.assertIsNotNone(src_key, f"unexpected Funding image {img['src']}")
            by_src[src_key] = img
        self.assertEqual(set(by_src), set(FUNDING_LOGOS))
        for src, (alt, href, width, height) in FUNDING_LOGOS.items():
            img = by_src[src]
            self.assertEqual(img["href"], href, src)
            self.assertEqual(img["alt"], alt, src)
            self.assertEqual((img["width"], img["height"]), (width, height), src)

    def test_about_uses_only_approved_logos(self):
        _, parser = self._parsed_about()

        rendered = [img["src"] for img in parser.images if img["in_about"]]
        basenames = [src.rsplit("/", 1)[-1] for src in rendered]
        for banned in BANNED_LOGOS:
            self.assertNotIn(
                banned,
                basenames,
                f"combined/incorrect logo {banned} rendered on About",
            )
        for src in rendered:
            self.assertTrue(
                any(src.endswith(k) for k in (*HISTORY_LOGOS, *FUNDING_LOGOS)),
                f"non-whitelisted image {src} rendered inside About content",
            )

    def test_contact_lists_current_institute_and_address(self):
        _, parser = self._parsed_about()
        text = parser.scoped_text("project-contact")

        for expected in (
            "Institute of Water Resources and Water Supply",
            "Eißendorfer Str. 40, 21073 Hamburg, Germany",
            "Hamburg University of Technology",
            "Bioresource Management Group",
            "info@bioresource-tools.net",
        ):
            self.assertIn(expected, text)
        self.assertNotIn(
            "Institute of Wastewater Management and Water Protection", text
        )
        self.assertNotIn("Eißendorfer Str. 42", text)

    def test_funding_retains_grant_details(self):
        _, parser = self._parsed_about()
        text = parser.scoped_text("project-funding")

        for expected in ("DATIpilot", "03DPS1185A", "03DPS1185B"):
            self.assertIn(expected, text)

    def test_logos_use_bounded_responsive_classes(self):
        _, parser = self._parsed_about()

        for img in parser.scoped_images("project-history"):
            classes = img["class"].split()
            self.assertIn("img-fluid", classes, img["src"])
            self.assertIn("about-logo", classes, img["src"])
        for img in parser.scoped_images("project-funding"):
            classes = img["class"].split()
            self.assertIn("img-fluid", classes, img["src"])
            self.assertIn("about-funder-logo", classes, img["src"])

    def test_interreg_project_logos_get_prominent_variant_classes(self):
        _, parser = self._parsed_about()

        logos = parser.scoped_images("project-history")
        interreg = [
            img
            for img in logos
            if any(img["src"].endswith(k) for k in INTERREG_PROJECT_LOGOS)
        ]
        others = [img for img in logos if img not in interreg]

        self.assertEqual(len(interreg), 2, logos)
        for img in interreg:
            self.assertIn("about-logo-interreg", img["class"].split(), img["src"])
            self.assertIn(
                "about-project-link-interreg",
                img["link_class"].split(),
                img["src"],
            )
        for img in others:
            self.assertNotIn("about-logo-interreg", img["class"].split(), img["src"])
            self.assertNotIn(
                "about-project-link-interreg", img["link_class"].split(), img["src"]
            )

    def test_standalone_secondary_logos_pair_with_interreg_lockups(self):
        response, parser = self._parsed_about()

        secondary = {
            "closecycle_logo.png": "https://www.interregnorthsea.eu/closecycle",
            "soilcom_logo.png": "https://northsearegion.eu/soilcom/",
        }
        logos = parser.scoped_images("project-history")
        marked = [
            img for img in logos if "about-logo-secondary" in img["class"].split()
        ]
        self.assertEqual(len(marked), 2, logos)
        for img in marked:
            basename = img["src"].rsplit("/", 1)[-1]
            self.assertIn(basename, secondary)
            self.assertEqual(img["href"], secondary[basename], basename)

        html = response.content.decode()
        self.assertEqual(html.count('class="about-project-branding"'), 2)

    def test_about_uses_sdv2_layout_and_stylesheets(self):
        response, parser = self._parsed_about()
        html = response.content.decode()

        for expected in (
            "css/sample_detail_v2.min.css",
            "css/about.min.css",
            'class="sdv2',
            "sdv2-hero",
            "sdv2-surface",
            "sdv2-layout",
            'id="project-history"',
            'aria-labelledby="project-history-heading"',
            'id="project-contact"',
            'id="project-funding"',
            'href="#project-history"',
            'href="#project-contact"',
            'href="#project-funding"',
            "sdv2-anchor-chip",
        ):
            self.assertIn(expected, html)

    def test_page_has_exactly_one_main_landmark(self):
        _, parser = self._parsed_about()

        self.assertEqual(parser.main_count, 1)

    def test_hero_announces_about_page(self):
        response, _ = self._parsed_about()
        html = response.content.decode()

        self.assertIn("sdv2-hero-kicker", html)
        self.assertIn("Bioresource Information Tool", html)
        self.assertIn("About BRIT", html)
        self.assertIn(
            "The people, projects and funding behind the Bioresource Information Tool.",
            html,
        )

    def test_about_css_defines_bounded_logo_rules(self):
        css_path = finders.find("css/about.css")
        self.assertIsNotNone(css_path, "about.css source not found")
        css = Path(css_path).read_text()

        for expected in (
            ".brit-about",
            ".about-logo",
            ".about-funder-logo",
            "object-fit: contain",
            "height: auto",
            "max-width",
            "scroll-margin-top",
            "var(--sdv2-anchor-offset)",
        ):
            self.assertIn(expected, css)

        for selector, expected in (
            ("about-project-link-interreg", ("32rem", "width", "flex-shrink: 0")),
            (
                "about-logo-interreg",
                ("width: 100%", "max-width: 100%", "max-height: none"),
            ),
            (
                "about-project-branding",
                ("display: flex", "flex-wrap: wrap", "align-items: center"),
            ),
            ("about-logo-secondary", ("max-width: 8rem", "max-height: 3rem")),
        ):
            match = re.search(rf"\.brit-about \.{selector}\s*\{{([^}}]*)\}}", css)
            self.assertIsNotNone(match, f"{selector} rule missing")
            for fragment in expected:
                self.assertIn(fragment, match.group(1), selector)

        self.assertIsNotNone(
            finders.find("css/about.min.css"),
            "about.min.css build artifact missing",
        )

    def test_new_logo_assets_resolve_and_match_native_dimensions(self):
        from PIL import Image

        for logo, expected_size in (
            ("img/brit_eu_logo.png", (1335, 387)),
            ("img/bmftr_logo.png", (506, 338)),
            ("img/interreg_with_closecycle_logo.png", (1237, 500)),
            ("img/interreg_with_soilcom_logo.png", (571, 236)),
            ("img/closecycle_logo.png", (506, 91)),
            ("img/soilcom_logo.png", (520, 130)),
        ):
            path = finders.find(logo)
            self.assertIsNotNone(path, f"{logo} not found by staticfiles")
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                self.assertEqual(image.size, expected_size)

    def test_interreg_svg_is_safe_self_contained_markup(self):
        path = finders.find("img/interreg_north_sea_logo.svg")
        self.assertIsNotNone(path, "interreg_north_sea_logo.svg not found")

        root = ElementTree.parse(path).getroot()
        self.assertTrue(root.tag.endswith("svg"))
        for element in root.iter():
            self.assertNotIn(element.tag.split("}")[-1], ("script", "foreignObject"))
            for value in element.attrib.values():
                self.assertNotIn("http", value)
                self.assertNotIn("url(", value.replace("url(#", ""))


class ReadmeProjectSectionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.readme = (REPO_ROOT / "README.md").read_text()

    def test_project_sections_appear_newest_first(self):
        sections = [
            "## The BRIT-EU project",
            "## The CLOSECYCLE project",
            "## The SOILCOM project",
            "## The FLEXIBI project",
        ]
        positions = [self.readme.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))

    def test_project_logos_are_linked_and_exist(self):
        for logo in ("brit_eu_funding_logo.png", "interreg_with_closecycle_logo.png"):
            local_path = f"brit/static/img/{logo}"
            self.assertIn(local_path, self.readme)
            self.assertTrue(
                (REPO_ROOT / local_path).is_file(),
                f"{local_path} referenced in README but missing",
            )

    def test_brit_eu_section_documents_funding(self):
        for expected in (
            "December 2024 to May 2026",
            "DATIpilot",
            "Federal Ministry of Research, Technology and Space",
            "BMFTR",
            "03DPS1185A",
            "03DPS1185B",
            "https://www.compostnetwork.info/brit-eu/",
        ):
            self.assertIn(expected, self.readme)

    def test_closecycle_section_documents_project(self):
        for expected in (
            "2024 to 2027",
            "Interreg North Sea",
            "Territorial Biorefinery Networks",
            "https://www.interregnorthsea.eu/closecycle",
        ):
            self.assertIn(expected, self.readme)

    def test_biem_section_lists_current_affiliation(self):
        section_start = self.readme.index("## The BIEM research group")
        section = self.readme[section_start:]

        self.assertIn("Institute of Water Resources and Water Supply", section)
        self.assertIn("Eißendorfer Str. 40, 21073 Hamburg, Germany", section)
        self.assertNotIn("Institute of Wastewater Management", section)
        self.assertNotIn("Eißendorfer Str. 42", section)

    def test_access_paragraph_lists_all_projects(self):
        access_start = self.readme.index("## Access")
        local_setup_start = self.readme.index("## Local setup")
        access_section = self.readme[access_start:local_setup_start]

        for expected in ("FLEXIBI", "SOILCOM", "CLOSECYCLE", "BRIT-EU", "BIEM"):
            self.assertIn(expected, access_section)
