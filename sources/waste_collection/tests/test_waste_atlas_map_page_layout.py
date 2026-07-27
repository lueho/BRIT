"""Per-map controls belong in the right-hand panel, not scattered around it.

The export buttons used to sit below a canvas that is taller than the viewport,
so they could only be found by scrolling past the whole map, and the option
toggles were injected into a bare div hanging below the panel's only card.
"""

from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

WASTE_ATLAS_DIR = Path(__file__).resolve().parents[1] / "waste_atlas"
CHOROPLETH_SCRIPT = WASTE_ATLAS_DIR / "static" / "js" / "waste_atlas_choropleth.js"
ATLAS_STYLESHEET = WASTE_ATLAS_DIR / "static" / "css" / "waste_atlas.css"

MAP_ROUTE = "waste-atlas-germany-collection-system-map"


class MapPageControlLayoutTests(TestCase):
    """Everything but the map itself is reachable without scrolling."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="layout-user", password="secret")
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user.groups.add(group)

    def setUp(self):
        self.client.force_login(self.user)

    def _content(self):
        response = self.client.get(reverse(MAP_ROUTE))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_no_controls_are_buried_below_the_canvas(self):
        content = self._content()

        self.assertNotIn('id="export-buttons"', content)
        canvas_end = content.index("</svg>")
        panel_start = content.index('id="atlas-side"')
        self.assertLess(canvas_end, panel_start)
        # Nothing interactive between the canvas and the controls panel.
        self.assertNotIn("<button", content[canvas_end:panel_start])

    def test_export_actions_live_in_the_controls_panel(self):
        content = self._content()

        self.assertIn('id="atlas-export"', content)
        self.assertLess(
            content.index('id="atlas-side"'),
            content.index('id="btn-export-svg"'),
        )

    def test_export_labels_are_short_with_descriptive_tooltips(self):
        content = self._content()

        self.assertIn("PNG (300 DPI)", content)
        self.assertNotIn("Download PNG (Word-ready, 300 DPI)", content)
        # The long explanation stays available on hover and to screen readers.
        self.assertIn('title="Download a PNG at 300 DPI, ready for Word"', content)
        self.assertIn('title="Download a vector SVG"', content)

    def test_map_options_live_in_a_titled_card(self):
        content = self._content()

        self.assertIn('id="atlas-map-options"', content)
        self.assertIn("Map options", content)
        card = content.split('id="atlas-map-options"')[1].split("</section>")[0]
        self.assertIn('id="atlas-map-tools"', card)

    def test_options_card_starts_hidden_until_a_toggle_is_added(self):
        """Only some maps offer quartiles or the conflict aid."""
        content = self._content()

        marker = content.index('id="atlas-map-options"')
        tag = content[
            content.rindex("<section", 0, marker) : content.index(">", marker)
        ]
        self.assertIn("hidden", tag)

    def test_navigation_stays_in_the_context_header(self):
        content = self._content()

        header = content.split('class="atlas-context-actions"')[1].split("</header>")[0]
        self.assertIn("Map overview", header)
        self.assertIn("atlas-mode-toggle", header)
        # Output is not navigation; downloads belong to the controls panel.
        self.assertNotIn("btn-export", header)


class MapPageControlLayoutAssetTests(SimpleTestCase):
    """The renderer and stylesheet back the panel layout."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()
        cls.stylesheet = ATLAS_STYLESHEET.read_text()

    def test_renderer_reveals_the_options_card_when_it_adds_a_toggle(self):
        self.assertIn("atlas-map-options", self.script)
        self.assertIn("removeAttribute('hidden')", self.script)

    def test_stylesheet_lays_out_the_panel_cards(self):
        self.assertIn(".atlas-side-card-title", self.stylesheet)
        self.assertIn(".atlas-export-actions", self.stylesheet)

    def test_toggles_are_flattened_inside_a_panel_card(self):
        """The toggle bar carries its own frame; nested boxes look wrong."""
        self.assertIn(".atlas-side-card .atlas-map-toggles", self.stylesheet)

    def test_legacy_europe_pages_keep_their_own_export_row(self):
        """karte0/karte41 have short canvases and no controls panel."""
        self.assertIn("#export-buttons", self.stylesheet)
